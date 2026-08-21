"""
trade_worker 설정 (환경변수 파싱).

worker 는 유저 1명당 1 프로세스(상시 daemon)로 뜬다. KIS_USER_ID 만 다르게.

※ 실전투자 전용이다 — 뜨면 즉시 실주문이 나간다. 예전에 있던 DRY_RUN 플래그는
  선언만 되고 주문 경로 어디서도 실제로 분기하지 않아 안전장치로 기능하지 못했다
  (docs_worker_mode_runtime_spec.md §10 참고). 그래서 아예 제거했다(2026-08-20).
  테스트/검증은 실계좌가 아닌 별도 계정으로 할 것.

| 변수 | 기본 | 설명 |
|------|------|------|
| KIS_USER_ID   | (필수) | 이 worker 가 담당할 유저 id (1/2/3) |
| BUY_TIME      | 09:00  | 매수 엔진 실행 시각 (KRX 정규장 시작, 시장가) |
| NXT_PREMARKET | true   | NXT 프리마켓 선매수 라운드 사용 여부 |
| NXT_BUY_TIME  | 08:00  | NXT 프리마켓 매수 시각 (프리마켓 08:00~08:50) |
| NXT_LIMIT_SLIP_PCT | 2.0 | 프리마켓 매수 지정가 = 전일종가 × (1+이 비율%) 후 호가단위 내림 |
| SELL_LIMIT_SLIP_PCT | 1.0 | NXT 장외(프리/애프터) 매도 지정가 = 체결가 × (1-이 비율%). 즉시 체결 유도 |
| MARKET        | KR     | 시장 코드 |
| BUY_BUDGET_RATIO | 0.98 | 매수 시 현금의 사용 비율 (수수료/호가 여유) |
| SYNC_WALLET_ON_BOOT | true | 부팅 시 실제 예수금으로 user_wallet 동기화 |
| SYNC_WALLET_ON_TRADE | true | 매수/매도 체결 직후 실제 예수금으로 재동기화 |
| SELL_RETRY_COOLDOWN_SEC | 60 | 매도 주문 실패 시 재시도 쿨다운(초) — 폭주 방지 |
| SELL_MAX_FAILS | 5 | 연속 매도 실패 이 횟수 도달 시 해당 종목 자동 비활성(수동 확인) |
| EXCHANGE | SOR | 실전 주문 거래소 라우팅: KRX / NXT / SOR(KRX+NXT 통합 최선체결) |
| BUY_FILL_WAIT_RETRIES | 3 | 매수 미체결(PENDING) 시 즉시 취소 전 추가 체결대기 재확인 횟수 |
| BUY_FILL_WAIT_SEC | 10 | 매수 체결대기 재확인 1회당 대기 시간(초) |
| WALLET_POLL_SEC | 10 | 계좌 예수금·보유종목 주기 갱신 간격(초). 0 이하면 폴링 비활성 |
"""
import os
from dataclasses import dataclass


def _bool(v, default):
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


@dataclass
class WorkerConfig:
    user_id: int
    buy_hour: int
    buy_minute: int
    nxt_premarket: bool
    nxt_buy_hour: int
    nxt_buy_minute: int
    nxt_limit_slip_pct: float
    sell_limit_slip_pct: float
    market: str
    buy_budget_ratio: float
    sync_wallet_on_boot: bool
    sync_wallet_on_trade: bool
    sell_retry_cooldown_sec: int
    sell_max_fails: int
    exchange: str
    buy_fill_wait_retries: int
    buy_fill_wait_sec: int
    wallet_poll_sec: int
    # user_options(s1_*) 변경 감지 주기(초). 0 이면 비활성 → 재기동해야 반영된다.
    settings_poll_sec: int


def load() -> WorkerConfig:
    uid = os.getenv("KIS_USER_ID")
    if not uid:
        raise RuntimeError("KIS_USER_ID 가 필요합니다. (worker 는 유저 1명당 1 프로세스)")

    buy_time = os.getenv("BUY_TIME", "09:00")
    hh, mm = (buy_time.split(":") + ["0"])[:2]

    nxt_time = os.getenv("NXT_BUY_TIME", "08:00")
    nhh, nmm = (nxt_time.split(":") + ["0"])[:2]

    return WorkerConfig(
        user_id=int(uid),
        buy_hour=int(hh),
        buy_minute=int(mm),
        nxt_premarket=_bool(os.getenv("NXT_PREMARKET"), True),
        nxt_buy_hour=int(nhh),
        nxt_buy_minute=int(nmm),
        nxt_limit_slip_pct=float(os.getenv("NXT_LIMIT_SLIP_PCT", "2.0")),
        sell_limit_slip_pct=float(os.getenv("SELL_LIMIT_SLIP_PCT", "1.0")),
        market=os.getenv("MARKET", "KR"),
        buy_budget_ratio=float(os.getenv("BUY_BUDGET_RATIO", "0.98")),
        sync_wallet_on_boot=_bool(os.getenv("SYNC_WALLET_ON_BOOT"), True),
        sync_wallet_on_trade=_bool(os.getenv("SYNC_WALLET_ON_TRADE"), True),
        sell_retry_cooldown_sec=int(os.getenv("SELL_RETRY_COOLDOWN_SEC", "60")),
        sell_max_fails=int(os.getenv("SELL_MAX_FAILS", "5")),
        exchange=(os.getenv("EXCHANGE", "SOR").upper() if os.getenv("EXCHANGE", "SOR").upper() in ("KRX", "NXT", "SOR") else "KRX"),
        buy_fill_wait_retries=int(os.getenv("BUY_FILL_WAIT_RETRIES", "5")),
        buy_fill_wait_sec=int(os.getenv("BUY_FILL_WAIT_SEC", "10")),
        wallet_poll_sec=int(os.getenv("WALLET_POLL_SEC", "30")),
        settings_poll_sec=int(os.getenv("SETTINGS_POLL_SEC", "60")),
    )
