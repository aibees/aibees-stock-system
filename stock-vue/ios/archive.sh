#!/usr/bin/env bash
# =============================================================================
# iOS 빌드 → Archive → (선택) TestFlight 업로드 자동화.
#
# Xcode GUI 의 Product > Archive + Organizer > Distribute App 과 같은 일을
# xcodebuild 로 수행한다. 어디서 실행해도 되도록 스크립트 위치 기준으로 이동한다.
#
#   ./ios/archive.sh                 웹빌드 + sync + archive + .ipa export
#   ./ios/archive.sh --upload        위 + App Store Connect(TestFlight) 업로드
#   ./ios/archive.sh --no-web        웹빌드/cap sync 생략 (dist 재사용)
#   ./ios/archive.sh --version 1.1   MARKETING_VERSION(표시 버전) 지정
#
# 빌드번호(CFBundleVersion)는 기본값이 현재시각(YYYYMMDDHHMM) 이다.
#   - pbxproj 의 CURRENT_PROJECT_VERSION 이 1 로 하드코딩돼 있어 그대로 올리면
#     "이미 사용된 빌드번호" 로 업로드가 거부된다.
#   - 파일을 고쳐 커밋하는 방식(agvtool)은 이 프로젝트에선 쓸 수 없다 —
#     VERSIONING_SYSTEM 이 설정돼 있지 않아 agvtool 이 동작하지 않는다.
#     그래서 빌드 시점에 build setting 을 덮어쓴다(파일 변경 없음 = 커밋 불필요).
#   - 시각 기반이라 항상 단조 증가하므로 중복이 구조적으로 불가능하다.
#   - BUILD_NUMBER 환경변수로 덮을 수 있다.
#
# 업로드(--upload)에 필요한 App Store Connect API 키 — 환경변수로 넘긴다:
#   ASC_KEY_ID      키 ID. AuthKey_XXXXXXXXXX.p8 의 XXXXXXXXXX 부분
#   ASC_ISSUER_ID   Issuer ID (App Store Connect > 사용자 및 액세스 > 통합)
#   ASC_KEY_PATH    .p8 파일 경로 (생략 시 stock-vue/AuthKey_<ASC_KEY_ID>.p8)
# 이 값들을 주면 archive 단계도 Apple 과 통신해 프로비저닝/인증서를 자동 갱신한다
# (-allowProvisioningUpdates). 주지 않으면 Xcode 에 로그인된 계정으로 서명한다.
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."          # stock-vue/
ROOT="$(pwd)"

PROJECT="ios/App/App.xcodeproj"
SCHEME="App"
TEAM_ID="454UQ5VBD9"             # pbxproj 의 DEVELOPMENT_TEAM
BUILD_DIR="$ROOT/ios/App/build"  # ios/.gitignore 에 이미 포함된 경로
ARCHIVE="$BUILD_DIR/App.xcarchive"
EXPORT_DIR="$BUILD_DIR/export"
PLIST="$BUILD_DIR/ExportOptions.plist"

DO_WEB=1
DO_UPLOAD=0
MARKETING_VERSION=""
BUILD_NUMBER="${BUILD_NUMBER:-$(date +%Y%m%d%H%M)}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --upload)  DO_UPLOAD=1; shift ;;
    --no-web)  DO_WEB=0; shift ;;
    --version) MARKETING_VERSION="${2:?--version 뒤에 버전이 필요합니다}"; shift 2 ;;
    -h|--help) sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "알 수 없는 옵션: $1 (--help 참고)" >&2; exit 2 ;;
  esac
done

# ── App Store Connect 인증 플래그 (3개가 모두 있을 때만 사용) ────────────────
ASC_KEY_ID="${ASC_KEY_ID:-}"
ASC_ISSUER_ID="${ASC_ISSUER_ID:-}"
ASC_KEY_PATH="${ASC_KEY_PATH:-}"
if [[ -n "$ASC_KEY_ID" && -z "$ASC_KEY_PATH" ]]; then
  ASC_KEY_PATH="$ROOT/AuthKey_${ASC_KEY_ID}.p8"
fi

# 빈 배열을 "${AUTH_ARGS[@]}" 로 펼치면 macOS 기본 bash 3.2 + set -u 에서 unbound variable 로 죽는다
# (ASC 키 없이 실행할 때). 아래 사용처는 ${AUTH_ARGS[@]+"${AUTH_ARGS[@]}"} 형태로 쓴다.
AUTH_ARGS=()
if [[ -n "$ASC_KEY_ID" && -n "$ASC_ISSUER_ID" && -n "$ASC_KEY_PATH" ]]; then
  if [[ ! -f "$ASC_KEY_PATH" ]]; then
    echo ">>> [ERROR] .p8 키를 찾을 수 없습니다: $ASC_KEY_PATH" >&2
    exit 1
  fi
  # -authenticationKeyPath 는 절대경로를 요구한다.
  AUTH_ARGS=(
    -allowProvisioningUpdates
    -authenticationKeyPath "$ASC_KEY_PATH"
    -authenticationKeyID "$ASC_KEY_ID"
    -authenticationKeyIssuerID "$ASC_ISSUER_ID"
  )
  echo ">>> App Store Connect API 키 사용 (keyID=$ASC_KEY_ID)"
elif [[ $DO_UPLOAD -eq 1 ]]; then
  echo ">>> [ERROR] --upload 에는 ASC_KEY_ID / ASC_ISSUER_ID 가 필요합니다." >&2
  echo "    예) ASC_KEY_ID=7PFAYQMD47 ASC_ISSUER_ID=<issuer-uuid> ./ios/archive.sh --upload" >&2
  exit 1
else
  echo ">>> ASC 키 없음 → Xcode 에 로그인된 계정으로 서명합니다."
fi

# ── 1) 웹 자산 빌드 + 네이티브 동기화 ────────────────────────────────────────
# cap:prod 가 .env.prd 로 빌드까지 수행한다(vite.config.js 의 mode 처리).
# 이 단계를 건너뛰면 "직전에 아무 env 로 구워둔 dist" 가 앱에 들어간다.
if [[ $DO_WEB -eq 1 ]]; then
  echo ">>> [1/4] 웹 빌드 + cap sync (npm run cap:prod)"
  npm run cap:prod
else
  echo ">>> [1/4] 웹 빌드 생략 (--no-web) — dist/ 를 그대로 사용합니다"
fi

# ── 2) Archive ───────────────────────────────────────────────────────────────
echo ">>> [2/4] xcodebuild archive (build=$BUILD_NUMBER${MARKETING_VERSION:+, version=$MARKETING_VERSION})"
rm -rf "$ARCHIVE" "$EXPORT_DIR"
mkdir -p "$BUILD_DIR"

VERSION_ARGS=(CURRENT_PROJECT_VERSION="$BUILD_NUMBER")
[[ -n "$MARKETING_VERSION" ]] && VERSION_ARGS+=(MARKETING_VERSION="$MARKETING_VERSION")

xcodebuild \
  -project "$PROJECT" \
  -scheme "$SCHEME" \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath "$ARCHIVE" \
  "${VERSION_ARGS[@]}" \
  ${AUTH_ARGS[@]+"${AUTH_ARGS[@]}"} \
  clean archive

# ── 3) ExportOptions.plist 생성 ──────────────────────────────────────────────
# 파일로 커밋하지 않고 매번 생성한다 — destination(export/upload) 이 옵션에 따라
# 달라지는데, 두 벌의 plist 를 두면 어느 쪽이 쓰였는지 헷갈린다.
DESTINATION="export"
[[ $DO_UPLOAD -eq 1 ]] && DESTINATION="upload"

echo ">>> [3/4] ExportOptions.plist (method=app-store-connect, destination=$DESTINATION)"
cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <!-- Xcode 15.3+ 이름. 예전 'app-store' 는 deprecated. -->
  <key>method</key><string>app-store-connect</string>
  <key>teamID</key><string>${TEAM_ID}</string>
  <key>signingStyle</key><string>automatic</string>
  <key>uploadSymbols</key><true/>
  <key>destination</key><string>${DESTINATION}</string>
  <!-- 기본값이 true 라서 Xcode 가 업로드 시 빌드번호를 또 손댄다.
       위에서 시각 기반으로 이미 정했으므로 끈다(로그의 번호와 실제 업로드 번호 일치). -->
  <key>manageAppVersionAndBuildNumber</key><false/>
</dict>
</plist>
PLIST_EOF
plutil -lint "$PLIST" >/dev/null

# ── 4) Export / Upload ───────────────────────────────────────────────────────
echo ">>> [4/4] xcodebuild -exportArchive"
xcodebuild -exportArchive \
  -archivePath "$ARCHIVE" \
  -exportOptionsPlist "$PLIST" \
  -exportPath "$EXPORT_DIR" \
  ${AUTH_ARGS[@]+"${AUTH_ARGS[@]}"}

echo ""
echo ">>> DONE  (build number = $BUILD_NUMBER)"
echo "    archive : $ARCHIVE"
if [[ $DO_UPLOAD -eq 1 ]]; then
  echo "    업로드 완료 → App Store Connect 에서 처리(수 분) 후 TestFlight 에 보입니다."
else
  echo "    ipa     : $(ls "$EXPORT_DIR"/*.ipa 2>/dev/null || echo "$EXPORT_DIR")"
  echo "    업로드까지 하려면 --upload 를 붙여 다시 실행하세요."
fi
