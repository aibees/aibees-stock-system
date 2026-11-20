#!/usr/bin/env bash
# =============================================================================
# 배포 스크립트 공통 함수 (py-secret-api/deploy.sh · py-yangbong-api/deploy.sh 가 source 한다).
# 단독으로 실행하지 않는다.
# =============================================================================

# ── 출력 ──
_c() { [[ -t 1 ]] && printf '\033[%sm' "$1" || true; }
step() { echo; echo "$(_c 1)>>> $*$(_c 0)"; }
ok()   { echo "  $(_c 32)✓$(_c 0) $*"; }
warn() { echo "  $(_c 33)!$(_c 0) $*"; WARNINGS=$((WARNINGS + 1)); }
fail() { echo "  $(_c 31)✗$(_c 0) $*"; FAILS=$((FAILS + 1)); }
die()  { echo; echo "$(_c 31)[중단]$(_c 0) $*" >&2; exit 1; }
WARNINGS=0
FAILS=0

# ── 1) git pull ──
# 저장소 루트에서 fast-forward 만 한다(로컬에서 고친 파일이 있으면 멈춘다 — 서버 clone 은 고치지 않는 게 원칙).
git_pull() {
  local root="$1"
  step "git pull ($(git -C "$root" rev-parse --abbrev-ref HEAD))"
  if [[ -n "$(git -C "$root" status --porcelain --untracked-files=no)" ]]; then
    git -C "$root" status --short --untracked-files=no | sed 's/^/  /'
    die "서버 clone 에 커밋되지 않은 변경이 있습니다. 확인 후 정리하거나 --no-pull 로 실행하세요."
  fi
  git -C "$root" pull --ff-only || die "git pull 실패(fast-forward 불가). 서버 clone 상태를 확인하세요."
  ok "커밋 $(git -C "$root" log -1 --format='%h %s')"
}

# ── 2) 점검 도우미 ──
need_cmd() { command -v "$1" >/dev/null 2>&1 || die "'$1' 명령이 없습니다."; }

# need_file <경로> <설명> — 없거나 폴더면 실패(docker 는 없는 마운트 원본을 빈 폴더로 만든다)
need_file() {
  if [[ -d "$1" ]]; then fail "$2 — '$1' 가 파일이 아니라 폴더입니다(마운트할 파일이 없을 때 docker 가 만든 빈 폴더일 수 있음). 지우고 파일을 두세요."
  elif [[ -f "$1" ]]; then ok "$2"
  else fail "$2 — 없음: $1"; fi
}

# env_value <파일> <키> — KEY=VALUE 한 줄에서 값만(따옴표 제거). 없으면 빈 문자열.
env_value() {
  [[ -f "$1" ]] || { echo ""; return; }
  # 순서: 키 떼기 → 줄 끝 주석(공백 뒤 #) 떼기 → 끝 공백 → 감싼 따옴표
  { grep -E "^[[:space:]]*(export[[:space:]]+)?$2=" "$1" || true; } | tail -1 \
    | sed -E "s/^[^=]*=//; s/[[:space:]]+#.*$//; s/[[:space:]]+$//; s/^[\"'](.*)[\"']$/\\1/"
  return 0   # 키가 없으면 grep 이 1 을 돌려준다 — set -euo pipefail 인 호출부가 조용히 멈추지 않게 성공으로 끝낸다
}

need_network() {
  if docker network inspect "$1" >/dev/null 2>&1; then ok "docker 네트워크 $1"
  else fail "docker 네트워크 $1 없음 — docker network create --subnet 172.21.0.0/16 $1"; fi
}

checks_done() {
  echo
  if [[ $FAILS -gt 0 ]]; then die "필수 항목 ${FAILS}개가 준비되지 않았습니다. 위 ✗ 를 해결한 뒤 다시 실행하세요."; fi
  [[ $WARNINGS -gt 0 ]] && echo "  경고 ${WARNINGS}개(!)는 배포를 막지 않습니다."
  return 0
}

# ── 컨테이너 교체 보조 ──
# adopt_container <compose 파일> <컨테이너 이름>…
#   compose 파일의 프로젝트 이름(name:)을 바꾸면, 옛 이름으로 떠 있는 같은 container_name 을
#   compose 가 남의 것으로 보고 "Conflict. The container name ... is already in use" 로 멈춘다.
#   다른 프로젝트 소속이면 지워서 새 프로젝트 이름으로 다시 만들게 한다(빌드가 끝난 뒤 부르므로 공백은 몇 초).
adopt_container() {
  local file="$1"; shift
  local want name cur
  want="$(sed -n 's/^name:[[:space:]]*//p' "$file" | head -1 | tr -d "\"'\r")"
  [[ -z "$want" ]] && return 0
  for name in "$@"; do
    cur="$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$name" 2>/dev/null || true)"
    if [[ -n "$cur" && "$cur" != "$want" ]] || { docker inspect "$name" >/dev/null 2>&1 && [[ -z "$cur" ]]; }; then
      warn "$name 이 다른 compose 프로젝트(${cur:-수동 실행}) 소속 → 지우고 '$want' 로 다시 만듭니다"
      docker rm -f "$name" >/dev/null
    fi
  done
}

# ── 3) 헬스체크 ──
# wait_up <컨테이너> — 15초 안에 Up 이 아니면 로그를 보여 주고 실패
wait_up() {
  local name="$1" status=""
  for _ in $(seq 1 15); do
    status="$(docker ps -a --filter "name=^/${name}$" --format '{{.Status}}')"
    [[ "$status" == Up* ]] && break
    sleep 1
  done
  if [[ "$status" == Up* ]]; then ok "$name: $status"
  else fail "$name: ${status:-없음}"; docker logs --tail 40 "$name" 2>&1 | sed 's/^/    /'; fi
}

# wait_http <URL> <설명> — 60초 안에 HTTP 응답(어떤 코드든)이 오면 통과. 코드를 echo 한다.
wait_http() {
  local url="$1" code=""
  for _ in $(seq 1 30); do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$url" || true)"
    [[ "$code" != "000" && -n "$code" ]] && { echo "$code"; return 0; }
    sleep 2
  done
  echo "000"; return 1
}
