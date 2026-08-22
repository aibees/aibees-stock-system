# iOS / Android 앱 테스트 방법 (Capacitor)

stock-vue → Capacitor 네이티브 앱 테스트 가이드. `android/`, `ios/` 폴더는 이미 스캐폴딩되어 있음.

---

## 0. 공통: 빌드 + 동기화 (코드/env 바꿀 때마다 매번)

```bash
cd stock-vue
cp .env.prd .env      # 실제 서버(stock.aibeesworld.com) 대상 빌드
yarn build             # dist/ 생성
npx cap sync           # dist/ → ios/android 네이티브 프로젝트로 복사 + 플러그인 동기화
```

- `npx cap sync ios` / `npx cap sync android` 로 한쪽만 동기화도 가능.
- **JS/Vue 코드나 .env 를 고칠 때마다 `yarn build && npx cap sync` 를 다시 해야** 앱에 반영됨. (핫리로드 아님)

---

## 1. iOS 테스트 (맥 + Xcode 필요)

### 1-1. 시뮬레이터 (제일 빠름, 계정 불필요)

```bash
npx cap open ios
```

- `ios/App/App.xcodeproj` 가 열림 (Podfile 없이 SPM 방식이라 `.xcworkspace` 아님, `.xcodeproj` 맞음).
- 상단 디바이스 선택에서 시뮬레이터(예: iPhone 15) 선택 → ▶ (Cmd+R).
- 서명/Apple ID 없이 바로 실행됨.

### 1-2. 실기기 테스트

1. Xcode > `App` 타겟 > Signing & Capabilities > Team = 본인 Apple ID(개인 팀, 무료 가능) 선택, "Automatically manage signing" 체크.
2. iPhone을 케이블로 연결 → 기기에서 "이 컴퓨터 신뢰" 확인.
3. iOS 16+ 라면: 아이폰 설정 > 개인정보 보호 및 보안 > 개발자 모드 켜기 → 재부팅.
4. Xcode 상단 디바이스 목록에서 실제 기기 선택 → ▶.
5. 무료 개인 팀은 앱이 **7일 후 만료** → 재실행하면 다시 설치됨. 기기당 주간 앱 설치 개수 제한(3개) 있음.

### 1-3. 디버깅 (콘솔/네트워크 확인)

Mac Safari: 환경설정 > 고급 > "메뉴 막대에서 개발자용 메뉴 보기" 켜기
→ 개발자용 메뉴 > [시뮬레이터/기기 이름] > localhost 선택 → Web Inspector 오픈.
- 콘솔 로그, 네트워크 탭에서 로그인·API 호출이 CORS 에러 없이 정상 응답하는지 확인.
- 실기기는 아이폰 설정 > Safari > 고급 > Web Inspector 켜야 함.

---

## 1-4. Live Reload (iOS, Vue 코드 고치면 시뮬레이터에 바로 반영)

기본 방식(`npx cap sync`)은 매번 빌드해야 반영됨. 아래는 vite dev 서버를 시뮬레이터가 직접 열게 해서 저장하자마자 반영되게 하는 방법.

> ⚠ `npx cap sync --config <file>` 은 이 CLI 버전(@capacitor/cli 8.x)에 없는 옵션임(`unknown option '--config'`). 대신 `capacitor.config.json`(Capacitor가 실제로 읽는 파일) 자체를 dev/prod 두 버전으로 바꿔치기하는 방식으로 함 — `capacitor.config.dev.json` / `capacitor.config.prod.json` 두 파일을 원본으로 두고, `package.json`에 스왑용 스크립트를 추가해둠.

```bash
cd stock-vue

# 터미널 1 — vite dev 서버 켜두기 (계속 실행 상태 유지)
yarn dev

# 터미널 2 — dev 모드로 전환 + sync
yarn cap:dev
npx cap open ios
```

Xcode에서 시뮬레이터로 Run(Cmd+R) → 앱이 번들이 아니라 `http://localhost:19010`(vite dev 서버)을 직접 로드함. 이후 Vue 파일 저장하면 vite HMR로 시뮬레이터 화면에 바로 반영됨(Xcode 재실행 불필요).

- **시뮬레이터 전용.** 실기기는 `localhost`가 아니라 맥의 LAN IP(예: `http://192.168.0.5:19010`)로 바꿔야 하고, 맥·아이폰이 같은 Wi-Fi여야 함. 필요하면 그때 다시 설정해줄게.
- **원래(번들) 방식으로 되돌리기**: `yarn cap:prod` — `capacitor.config.json`을 운영용 내용으로 복원하고 다시 sync함. **실기기 배포/App Store 빌드 전엔 반드시 이거 먼저 돌릴 것** (dev 상태로 두면 로컬 vite 서버를 찾다가 흰 화면만 뜸).
- vite dev 서버(`yarn dev`)를 끄면 앱이 흰 화면만 뜸 — 계속 켜둔 상태로 테스트.

---

## 2. Android 테스트 (Android Studio 필요, Win/Mac/Linux 다 가능)

### 2-1. 에뮬레이터

```bash
npx cap open android
```

- Android Studio가 `android/` 프로젝트를 염 (이미 한 번 빌드된 이력 있음 — `.gradle` 캐시 존재).
- 상단 툴바에서 AVD(에뮬레이터) 없으면 Device Manager > Create Device 로 하나 생성 (예: Pixel 8, API 34).
- ▶(Run) 누르면 에뮬레이터 부팅 후 자동 설치·실행.

### 2-2. 실기기 테스트

1. 안드로이드 폰: 설정 > 휴대전화 정보 > 빌드번호 7번 연타 → 개발자 옵션 활성화.
2. 설정 > 개발자 옵션 > USB 디버깅 켜기.
3. 케이블로 PC 연결 → 폰에서 "USB 디버깅 허용" 팝업 확인.
4. Android Studio 상단 디바이스 목록에 기기 뜨면 선택 후 ▶.
5. 별도 계정/서명 없이 바로 설치됨(디버그 빌드는 자동 서명).

### 2-3. 디버깅 (콘솔/네트워크 확인)

Chrome 주소창에 `chrome://inspect#devices` 입력 (PC의 Chrome, USB 연결된 상태)
→ 실행 중인 앱의 WebView가 목록에 뜸 → "inspect" 클릭 → Chrome DevTools로 콘솔/네트워크 확인.
에뮬레이터도 동일하게 잡힘.

---

## 3. 테스트 시 꼭 확인할 것 (최근 수정 사항 검증)

앱은 웹과 달리 `https://localhost`(iOS/Android WebView) 라는 별개 origin에서 뜨기 때문에, API 서버(`stock.aibeesworld.com`)로의 모든 호출이 진짜 cross-origin이 됨. 아래를 Web Inspector / DevTools 네트워크 탭에서 확인:

- [ ] 이메일 로그인 (`/api/oauth/email`) — 정상 응답 오는지, CORS 에러 안 뜨는지
      → ROOT 서버(별도 저장소, 5556) CORS 설정에 `Authorization` 헤더 허용 안 돼있으면 여기서 막힘.
- [ ] 로그인 후 메뉴 로드 (`/api/v1/master/menus`)
- [ ] 매도 수기등록 화면 — 등록/조회/취소 (`/api/v1/auto-trade/manual-sell*`, py-stock-batch 5557)
      → 오늘 nginx `/api/v1/auto-trade` 라우팅 + CORS `Authorization` 허용 수정한 부분.

CORS 에러가 뜨면: Web Inspector/DevTools 콘솔에 `has been blocked by CORS policy` 문구로 바로 확인 가능 — 어느 API가 막혔는지 그대로 알려줌.

---

## 4. 참고

- `capacitor.config.json` 의 `server` 설정에 URL이 없으므로 앱은 항상 **번들된 `dist/`** 를 로드함 (라이브 리로드 아님) — 실제 배포와 가장 가까운 방식으로 테스트하는 것.
- 네이버/카카오 로그인 버튼은 현재 "준비중" stub이라 앱에서도 그대로 동작 안 함(정상).

---

## 5. 실제 배포 패키지 만들기 (.ipa / .aab)

시뮬레이터/USB 실행이 아니라 **TestFlight·App Store, Play Store(또는 사내 배포)용 설치 파일**을 뽑는 방법. 공통 전제: 반드시 운영 설정(`yarn cap:prod`)으로 빌드할 것 — dev 상태로 패키징하면 로컬 vite 서버를 찾다가 흰 화면만 뜨는 앱이 나감.

```bash
cd stock-vue
yarn cap:prod        # capacitor.config.json 을 운영용으로 (혹시 dev 상태였다면 필수)
yarn build && npx cap sync
```

### 5-1. iOS — .ipa (App Store / TestFlight)

**유료 Apple Developer Program 필요 ($99/년)** — 무료 개인 팀으로는 시뮬레이터/USB 실행만 되고 TestFlight·App Store 배포는 불가능함.

1. [Apple Developer](https://developer.apple.com) 가입 (유료) → [App Store Connect](https://appstoreconnect.apple.com)에서 새 앱 등록. Bundle ID는 `capacitor.config.json`의 `appId` 그대로: `com.aibeesworld.stock`.
2. Xcode에서 `npx cap open ios` → 상단 디바이스를 **"Any iOS Device (arm64)"** 로 선택 (시뮬레이터 선택된 채로는 Archive 메뉴가 비활성화됨).
3. Signing & Capabilities에서 Team을 유료 계정으로 변경, "Automatically manage signing" 유지.
4. General 탭에서 버전(Version)·빌드(Build) 번호 확인 — 업데이트할 때마다 최소 Build 번호는 올려야 스토어가 새 버전으로 인식함.
5. 메뉴 `Product > Archive` → 빌드 끝나면 Organizer 창이 자동으로 뜸.
6. Organizer에서 `Distribute App` → 배포 방식 선택:
   - **App Store Connect** — 심사 제출용. TestFlight(내부/외부 테스터 베타 배포)도 이 경로로 먼저 올라감.
   - **Ad Hoc** — 등록해둔 특정 기기(UDID)에만 설치. 스토어 심사 없이 팀 내부 테스트용으로 빠름. 기기 최대 100대 제한.
   - **Development** — 개발자 인증서로 서명, 로컬 배포용.
7. App Store Connect 경로면 앱 아이콘/스크린샷/개인정보처리방침 URL/심사 정보 등을 채운 뒤 심사 제출 (보통 1~3일 소요).

### 5-2. Android — .aab (Play Store)

**Google Play Console 계정 필요 ($25 1회 등록비, 평생)**. 사내 배포(스토어 안 거침)만 할 거면 이 계정 없이도 서명된 `.apk`만 뽑아서 직접 배포 가능.

1. Android Studio에서 `npx cap open android`.
2. 메뉴 `Build > Generate Signed Bundle / APK` → **Android App Bundle (.aab)** 선택 (Play Store는 이제 .aab 필수, .apk는 사내 직접배포용).
3. 서명 키(keystore) — 처음이면 `Create new...`로 생성:
   - keystore 파일 경로, 비밀번호, key alias, alias 비밀번호 설정.
   - **⚠ 이 keystore 파일 + 비밀번호는 절대 분실하면 안 됨** — 분실 시 이후 업데이트를 같은 앱으로 올릴 방법이 없어져서 완전히 새 앱으로 다시 등록해야 함. 안전한 곳(비밀번호 관리자 등)에 백업 필수.
4. Build Variant는 `release` 선택 → Finish → `.aab` 생성됨 (경로는 Android Studio가 완료 알림에 표시).
5. [Play Console](https://play.google.com/console)에서 앱 등록 → 먼저 **내부 테스트(Internal testing)** 트랙에 `.aab` 업로드해서 검증 권장 → 문제없으면 프로덕션 트랙으로 승격. 첫 심사는 보통 며칠 걸릴 수 있음.

### 5-3. 공통 체크리스트

- [ ] `yarn cap:prod` 로 운영 설정 상태 확인 (dev config로 패키징하면 안 됨)
- [ ] `.env.prd` 기준으로 빌드됐는지 확인 (`stock.aibeesworld.com` 대상)
- [ ] 버전/빌드 번호 갱신 (iOS: Xcode General 탭, Android: `android/app/build.gradle`의 `versionCode`/`versionName`)
- [ ] 앱 아이콘/스플래시는 이미 준비돼 있음 (`ios/App/App/Assets.xcassets`, `android/app/src/main/res/mipmap-*`) — 로고 바꾸고 싶으면 별도로 알려줘, `@capacitor/assets` 같은 도구로 한번에 재생성 가능
