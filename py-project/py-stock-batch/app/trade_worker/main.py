"""
trade_worker 진입점 (유저 1명당 1 프로세스, 상시 daemon).

실행:
    KIS_USER_ID=1 python -m app.trade_worker.main

구성:
  - KisEngine(user_id) 으로 자기 유저 KIS 실전 세션 생성 (keyLoader → DB key).
  - 매수 엔진: APScheduler cron(BUY_TIME, 기본 09:00) → 개장 일봉정리 + 시장가 매수.
  - 매도 엔진: 실시간 소켓 구독(stop/target/trail 라인 감시).
  - 안전장치: DRY_RUN 기본 true (실주문 전 로그만).

메인 py-stock-batch(gunicorn 웹앱)과 별개의 진입점이다.
"""
import logging
import signal
import threading
from datetime import datetime
from decimal import Decimal

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pytz import timezone

from app.ext_services.kis.KisEngine import KisEngine
from app.trade_worker import config
from app.trade_worker.broker import Broker
from app.trade_worker.buy_executor import BuyExecutor
from app.trade_worker.notifier import Notifier
from app.trade_worker.position_strategy import SellStrategy
from app.trade_worker.repository import Repository
from app.trade_worker.sell_executor import SellExecutor
from app.trade_worker.wallet_sync import reconcile_wallet

_KST = timezone("Asia/Seoul")


def _kst_converter(timestamp):
    """로그 asctime 을 KST(Asia/Seoul) 로 변환."""
    return datetime.fromtimestamp(timestamp, _KST).timetuple()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
# 컨테이너 TZ(UTC) 무관하게 로그 시각을 KST 로 출력
logging.Formatter.converter = staticmethod(_kst_converter)
log = logging.getLogger("trade_worker")

_stop = threading.Event()


def _handle_signal(signum, frame):
    log.info("종료 시그널(%s) 수신 → 정리 중", signum)
    _stop.set()


def _boot_balance_check(cfg, broker, repo):
    """부팅 시 실제 KIS 계좌를 조회해:
      1) 예수금(현금)을 DB user_wallet 과 대조/동기화
      2) 보유 종목(있으면)을 조회해 표시 + 총자산 계산
      3) (선택) 보유 종목을 active 포지션으로 반영
    """
    # ── 1) 예수금(현금) ──────────────────────────────────────────────
    actual = broker.account_cash()
    db_bal = repo.get_wallet_balance(cfg.user_id)
    if actual is None:
        log.warning("[부팅] 실제 예수금 조회 실패 → DB user_wallet(%s) 그대로 사용", db_bal)
    else:
        log.info("[부팅] 실제 예수금=%s · DB user_wallet=%s", actual, db_bal)
        if actual != db_bal and not cfg.sync_wallet_on_boot:
            log.warning("[부팅] 잔고 불일치(실제 %s ≠ DB %s), SYNC_WALLET_ON_BOOT=false → 예수금 미동기화",
                        actual, db_bal)

    cash = actual if actual is not None else db_bal

    # ── 2) 보유 종목 조회/표시 ───────────────────────────────────────
    holdings = broker.account_holdings()
    stock_amount = None
    total_asset = None
    if holdings is not None:
        try:
            repo.replace_holdings(cfg.user_id, holdings)  # 종목별 내역 user_holdings 갱신
        except Exception as e:  # noqa: BLE001
            log.warning("[부팅] user_holdings 갱신 실패: %s", e)
    if holdings:
        stock_amount = sum((h["eval_amount"] for h in holdings), Decimal(0))
        total_asset = (cash or Decimal(0)) + stock_amount
        log.info("[부팅] 보유 종목 %d개 · 평가합계=%s", len(holdings), stock_amount)
        for h in holdings:
            log.info("        · %s(%s) %s주 · 평단=%s 현재=%s 평가=%s 손익=%s",
                     h["name"], h["symbol"], h["qty"], h["avg_price"],
                     h["cur_price"], h["eval_amount"], h["profit"])
        log.info("[부팅] 총자산 ≈ 예수금 %s + 보유평가 %s = %s", cash, stock_amount, total_asset)
    elif holdings is not None:
        stock_amount = Decimal(0)
        total_asset = cash or Decimal(0)
        log.info("[부팅] 보유 종목 없음 (예수금만: %s)", cash)

    # ── 3) user_wallet 스냅샷 갱신(예수금+보유주식평가+총자산) ─────────
    #   예수금은 sync_wallet_on_boot 일 때만 실제값으로 덮어씀.
    cash_to_write = actual if (actual is not None and cfg.sync_wallet_on_boot) else None
    if cash_to_write is not None or stock_amount is not None:
        try:
            repo.set_wallet_snapshot(cfg.user_id, cash=cash_to_write,
                                     stock_amount=stock_amount, total_asset=total_asset)
            log.info("[부팅] user_wallet 스냅샷 갱신(예수금=%s 보유평가=%s 총자산=%s)",
                     cash_to_write if cash_to_write is not None else "(유지)", stock_amount, total_asset)
        except Exception as e:  # noqa: BLE001
            log.warning("[부팅] user_wallet 스냅샷 갱신 실패: %s", e)
        try:
            repo.insert_worker_log(cfg.user_id, "boot", "INFO",
                                   f"예수금={cash} 보유평가={stock_amount} 총자산={total_asset}")
        except Exception:  # noqa: BLE001
            pass

def _reconcile_positions(cfg, broker, repo, strategy):
    """부팅 시 실제 계좌 보유종목을 trade_worker_position(HOLDING)으로 반영.
      - 실제 보유인데 테이블에 없음 → HOLDING 신규 등록(평단=계좌 평균단가) + 초기 라인
      - 테이블 HOLDING인데 실제 미보유 → 외부청산으로 종료(SOLD)
      - 수량 불일치 → 실제 수량으로 갱신
    ※ KIS balance 엔 실제 매수일 정보가 없어 entry_ymd 는 부팅일로 기록(타임스탑은 그 시점부터 카운트).
    """
    if not cfg.reconcile_holdings_on_boot:
        return
    holdings = broker.account_holdings()
    if holdings is None:
        log.warning("[부팅] 보유종목 조회 실패 → 포지션 반영 skip")
        return
    held = {h["symbol"]: h for h in holdings}
    rows = repo.get_holding_positions(cfg.user_id)
    holding = {p["stock_code"]: p for p in rows}

    # 1) 실제 보유 → 테이블에 없으면 등록(adopt)
    for code, h in held.items():
        if code in holding:
            # 수량 불일치 보정
            if Decimal(str(holding[code].get("hold_qty") or 0)) != Decimal(str(h["qty"])):
                repo.update_position_qty(cfg.user_id, code, Decimal(str(h["qty"])))
                log.info("[부팅] %s 수량 보정 → %s", code, h["qty"])
            continue
        repo.open_position(cfg.user_id, code, h.get("name") or "",
                           Decimal(str(h["avg_price"])), Decimal(str(h["qty"])))
        if strategy:
            try:
                lines = strategy.initial_lines(code, float(h["avg_price"]))
                repo.update_position_state(cfg.user_id, code, lines)
            except Exception as e:  # noqa: BLE001
                log.warning("[부팅] %s 초기 라인 계산 실패: %s", code, e)
        log.info("[부팅] 보유종목 %s(%s) → HOLDING 반영 (평단=%s qty=%s)",
                 h.get("name"), code, h["avg_price"], h["qty"])

    # 2) 테이블 HOLDING인데 실제 미보유 → 외부청산 종료
    for code in holding.keys() - held.keys():
        repo.close_position(cfg.user_id, code, Decimal(0), Decimal(0), "EXTERNAL_CLOSED")
        log.warning("[부팅] %s 실제 미보유 → 포지션 종료(외부청산)", code)


def main():

    cfg = config.load()
    log.info("trade_worker 시작 · user_id=%s · mode=%s · buy=%02d:%02d",
             cfg.user_id, cfg.mode, cfg.buy_hour, cfg.buy_minute)

    # 자기 유저 KIS 세션 (KIS_USER_ID → keyLoader → DB key). 실전 전용.
    engine = KisEngine(user_id=cfg.user_id)

    broker = Broker(engine.kis) # engine.kis = pyKis

    repo = Repository()

    # 체결 알림: 텔레그램 우선, 실패 시 이메일 fallback
    notifier = Notifier(repo.get_user_notify(cfg.user_id), mode_tag=cfg.mode)

    # 매도 전략(KospiStrategy1 재사용) — 라인/액션 자체 계산
    strategy = SellStrategy(engine, cfg.user_id)

    buy = BuyExecutor(cfg, broker, repo, notifier, strategy=strategy)
    sell = SellExecutor(cfg, broker, repo, notifier, strategy=strategy)

    # 부팅 시 실제 계좌 예수금 확인 + DB user_wallet 대조/동기화 + 보유종목 표시
    _boot_balance_check(cfg, broker, repo)

    # 부팅 시 실제 보유종목을 trade_worker_position(HOLDING)으로 반영
    _reconcile_positions(cfg, broker, repo, strategy)

    # 체결통보 구독(주문번호별 체결 누적) — 로깅 훅은 매도엔진에 위임
    broker.start_fill_tracking(on_event=sell._on_execution)

    # 매도: 실시간 시세 소켓 구독 시작
    sell.start()

    # 매수: 09:00 cron (개장 시 일봉 SELL 정리 → 매수)
    scheduler = BackgroundScheduler(timezone=timezone("Asia/Seoul"))

    def _open_routine():
        # 장 개시(개장일) 확인 — 주말 제외 + KIS 휴장일 API(opnd_yn).
        # 휴장이면 라인 재계산/매도/매수 전체를 건너뛴다(개장일에만 루틴 수행).
        now_kst = datetime.now(_KST)
        if now_kst.weekday() >= 5:   # 5=토, 6=일
            log.info("[개장] 주말(%s) → 루틴 skip", now_kst.strftime("%Y-%m-%d"))
            return
        trading = broker.is_trading_day()
        if trading is False:
            log.info("[개장] 휴장일(%s) → 루틴 skip", now_kst.strftime("%Y-%m-%d"))
            return
        if trading is None:
            log.warning("[개장] 개장일 확인 실패 → 평일이므로 진행")
        try:
            sell.reload_positions()      # HOLDING 포지션 재적재(감시 대상 갱신)
            sell.refresh_positions()     # KospiStrategy1로 라인/액션 재계산 + SELL이면 즉시 매도
            buy.run()                    # 매수
        except Exception as e:  # noqa: BLE001
            log.exception("개장 루틴 실패: %s", e)

    scheduler.add_job(_open_routine, CronTrigger(hour=cfg.buy_hour, minute=cfg.buy_minute),
                      id="open_routine", max_instances=1)

    # 계좌 예수금·보유종목 주기 갱신 (기본 10초). WALLET_POLL_SEC<=0 이면 비활성.
    #   reconcile_wallet: 실제 KIS 계좌 조회 → user_wallet(예수금·보유평가·총자산) + user_holdings 갱신.
    #   coalesce=True/max_instances=1 : 지연 시 폴링이 밀려 쌓이지 않도록 1건만 유지.
    #   가드: 평일 && 08:00~20:00(KST) && 개장일(휴장 제외)에만 실제 조회.
    #        is_trading_day 는 KIS API 호출이라 날짜별 1회만 조회해 캐시한다.
    _POLL_START_HOUR, _POLL_END_HOUR = 8, 20
    _trading_cache: dict = {}

    def _is_trading_day_cached(now_kst) -> bool:
        ymd = now_kst.strftime("%Y-%m-%d")
        if ymd not in _trading_cache:
            trading = broker.is_trading_day()
            # None(확인 실패)은 평일이므로 진행(fail-open) — 캐시하지 않고 다음에 재시도
            if trading is None:
                return True
            _trading_cache.clear()          # 날짜 넘어가면 이전 캐시 정리
            _trading_cache[ymd] = trading
        return _trading_cache[ymd]

    def _poll_wallet():
        now_kst = datetime.now(_KST)
        if now_kst.weekday() >= 5:                                  # 주말
            return
        if not (_POLL_START_HOUR <= now_kst.hour < _POLL_END_HOUR):  # 08:00~19:59
            return
        if not _is_trading_day_cached(now_kst):                     # 휴장일
            return
        try:
            reconcile_wallet(broker, repo, cfg.user_id, sync=True, tag="poll")
        except Exception as e:  # noqa: BLE001
            log.warning("[poll] 계좌 갱신 실패: %s", e)

    if cfg.wallet_poll_sec > 0:
        scheduler.add_job(_poll_wallet, IntervalTrigger(seconds=cfg.wallet_poll_sec),
                          id="wallet_poll", max_instances=1, coalesce=True)
        log.info("계좌 주기 갱신 등록: %d초마다", cfg.wallet_poll_sec)

    scheduler.start()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    log.info("trade_worker 대기 (Ctrl+C 로 종료)")
    _stop.wait()

    scheduler.shutdown(wait=False)
    log.info("trade_worker 종료")


if __name__ == "__main__":
    main()
