"""
trade_worker 진입점 (유저 1명당 1 프로세스, 상시 daemon).

실행:
    KIS_USER_ID=1 python -m app.trade_worker.main

구성:
  - KisEngine(user_id) 으로 자기 유저 KIS 실전 세션 생성 (keyLoader → DB key).
  - 매수 엔진(이중화):
      · NXT_BUY_TIME(기본 08:00) → NXT 프리마켓 지정가 선매수(1위가 NXT 대상일 때만).
      · BUY_TIME(기본 09:00)     → 개장 일봉정리 + KRX 정규장 시장가 매수.
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


# force=True 필수.
#   위쪽 import 로 딸려오는 pykis 가 import 시점에 인자 없는 logging.basicConfig() 를
#   호출해 루트 로거에 핸들러를 붙이고 레벨을 WARNING 으로 굳혀버린다.
#   basicConfig 는 루트에 핸들러가 이미 있으면 no-op 이라, force 없이는
#   이 설정이 통째로 무시되어 trade_worker 의 INFO 로그가 전부 사라진다.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    force=True,
)
# 컨테이너 TZ(UTC) 무관하게 로그 시각을 KST 로 출력
logging.Formatter.converter = staticmethod(_kst_converter)
# pykis 는 자체 핸들러를 갖고 있어 propagate 를 두면 같은 줄이 두 번 찍힌다.
logging.getLogger("pykis").propagate = False
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

def _reconcile_positions(cfg, broker, repo):
    """부팅 시 **worker 가 직접 매수한 포지션**(trade_worker_position)만 계좌와 대조한다.

      - 테이블 HOLDING인데 실제 미보유 → 외부청산으로 종료(SOLD)   ← 안전장치
      - 수량 불일치 → 실제 수량으로 갱신

    ※ 수동매수(HTS·MTS 등 타채널) 보유종목은 **흡수하지 않는다**.
      worker 는 자기가 산 것만 감시·매도한다. 계좌 실제 보유 전체는
      user_holdings(wallet_sync) 에 미러링되며 그쪽이 조회용 정본이다.
    """
    holdings = broker.account_holdings()
    if holdings is None:
        log.warning("[부팅] 보유종목 조회 실패 → 포지션 대조 skip")
        return
    held = {h["symbol"]: h for h in holdings}
    rows = repo.get_holding_positions(cfg.user_id)
    holding = {p["stock_code"]: p for p in rows}

    # 1) AUTO 포지션 수량 보정 (부분 체결/부분 매도 반영)
    for code, p in holding.items():
        h = held.get(code)
        if h is None:
            continue
        if Decimal(str(p.get("hold_qty") or 0)) != Decimal(str(h["qty"])):
            repo.update_position_qty(cfg.user_id, code, Decimal(str(h["qty"])))
            log.info("[부팅] %s 수량 보정 → %s", code, h["qty"])

    # 2) 테이블 HOLDING인데 실제 미보유 → 외부청산 종료
    #    (worker 가 산 종목을 사용자가 HTS 로 먼저 판 경우. 정리하지 않으면
    #     이미 판 종목에 매도 주문을 반복해 연속 실패 → 자동 비활성으로 이어진다)
    for code in holding.keys() - held.keys():
        repo.close_position(cfg.user_id, code, Decimal(0), Decimal(0), "EXTERNAL_CLOSED")
        log.warning("[부팅] %s 실제 미보유 → 포지션 종료(외부청산)", code)

    # 3) 흡수하지 않은 계좌 보유(수동매수) 는 감시 대상이 아님을 명시적으로 남긴다
    untracked = held.keys() - holding.keys()
    if untracked:
        log.info("[부팅] 감시 제외(수동보유) %d종목: %s",
                 len(untracked), ", ".join(sorted(untracked)))


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

    # 부팅 시 worker 자기 포지션만 계좌와 대조(수량 보정 / 외부청산 정리).
    # 수동매수 보유종목은 흡수하지 않는다.
    _reconcile_positions(cfg, broker, repo)

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
            # 매수는 이 루틴의 마지막이라, 여기서 다시 적재하지 않으면 당일 산 종목이
            # sell 의 감시 대상(positions)·소켓 구독에 들어가지 않는다.
            # → 진입 당일 하루 종일 손절/익절이 돌지 않는 사각지대가 생긴다.
            # reset_sold=False: 위 refresh 에서 이미 판 종목의 _sold 마킹을 지우지 않는다.
            sell.reload_positions(reset_sold=False)
        except Exception as e:  # noqa: BLE001
            log.exception("개장 루틴 실패: %s", e)

    # ※ CronTrigger 에 timezone 을 반드시 명시할 것.
    #   APScheduler 3.x 의 BaseScheduler._create_trigger 는 "이미 생성된 trigger 인스턴스"를
    #   그대로 반환한다(=scheduler.timezone 을 주입하지 않는다). timezone 이 주입되는 건
    #   add_job(func, 'cron', hour=..) 처럼 문자열 alias 로 넘겼을 때뿐이다.
    #   따라서 여기서 생략하면 CronTrigger 는 get_localzone() = 컨테이너 TZ(UTC) 로 떨어져
    #   09:00 이 09:00 UTC(=18:00 KST) 로 돌아 "장운영시간이 아닙니다"(KIOK0320) 가 난다.
    scheduler.add_job(_open_routine,
                      CronTrigger(hour=cfg.buy_hour, minute=cfg.buy_minute, timezone=_KST),
                      id="open_routine", max_instances=1)
    log.info("개장 루틴 등록: 매일 %02d:%02d (KST) · 주말/휴장일 skip",
             cfg.buy_hour, cfg.buy_minute)

    # ── NXT 프리마켓 선매수 라운드 (08:00) ──────────────────────────
    #   넥스트레이드 프리마켓은 08:00~08:50, **지정가 호가만** 허용한다.
    #   매수만 수행한다. 매도(라인 재계산·즉시매도)는 09:00 루틴에 그대로 둔다 —
    #   보유종목이 KRX 전용이면 이 시간대 매도 주문이 '장운영시간이 아닙니다'로 실패한다.
    def _premarket_routine():
        now_kst = datetime.now(_KST)
        if now_kst.weekday() >= 5:
            return
        trading = broker.is_trading_day()
        if trading is False:
            log.info("[프리마켓] 휴장일(%s) → skip", now_kst.strftime("%Y-%m-%d"))
            return
        try:
            buy.run(premarket=True)
            sell.reload_positions(reset_sold=False)   # 프리마켓 체결분 즉시 감시 등록
        except Exception as e:  # noqa: BLE001
            log.exception("프리마켓 루틴 실패: %s", e)

    if cfg.nxt_premarket:
        scheduler.add_job(_premarket_routine,
                          CronTrigger(hour=cfg.nxt_buy_hour, minute=cfg.nxt_buy_minute,
                                      timezone=_KST),
                          id="premarket_routine", max_instances=1)
        log.info("NXT 프리마켓 매수 등록: 매일 %02d:%02d (KST) · 지정가(전일종가+%s%%) · 1위가 NXT 대상일 때만",
                 cfg.nxt_buy_hour, cfg.nxt_buy_minute, cfg.nxt_limit_slip_pct)
    else:
        log.info("NXT 프리마켓 매수 비활성(NXT_PREMARKET=false)")

    # ── 세션 종료 시 고점(peak_high) flush ──────────────────────────
    #   장중에는 SellExecutor 가 소켓 체결가로 peak_high 를 메모리에서만 갱신한다
    #   (틱마다 DB UPDATE 를 하면 부하가 감당되지 않는다).
    #   세션이 닫히는 시점에 1회 저장해 다음날 reload_positions 가 이어받게 한다.
    #     · 15:31 : KRX 마감(15:30) 직후 — KRX 전용 종목의 당일 고점 확정
    #     · 20:01 : NXT 애프터마켓 마감(20:00) 직후 — NXT 대상 종목까지 확정
    #   두 job 모두 전 종목을 훑지만 flush_peaks 는 dirty 로 표시된 종목만 쓰므로
    #   15:31 에 저장된 종목은 20:01 에 중복 저장되지 않는다(그 사이 고점 갱신분만 저장).
    def _flush_peaks(tag: str):
        now_kst = datetime.now(_KST)
        if now_kst.weekday() >= 5:
            return
        if not _is_trading_day_cached(now_kst):
            return
        try:
            sell.flush_peaks(tag)
        except Exception as e:  # noqa: BLE001
            log.exception("고점 flush(%s) 실패: %s", tag, e)

    scheduler.add_job(lambda: _flush_peaks("KRX마감"),
                      CronTrigger(hour=15, minute=31, timezone=_KST),
                      id="peak_flush_krx", max_instances=1)
    scheduler.add_job(lambda: _flush_peaks("NXT마감"),
                      CronTrigger(hour=20, minute=1, timezone=_KST),
                      id="peak_flush_nxt", max_instances=1)
    log.info("고점 flush 등록: 15:31 / 20:01 (KST) · 주말·휴장일 skip")

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
    else:
        log.info("계좌 주기 갱신 비활성 (WALLET_POLL_SEC=%d)", cfg.wallet_poll_sec)

    # ── 설정(user_options s1_*) 변경 감지 ──────────────────────────────
    #  worker 는 데몬이라 부팅 시 configure() 한 파라미터가 그대로 굳는다.
    #  이 폴링이 없으면 화면에서 매도 조건을 바꿔도 재기동 전까지 반영되지 않는다.
    #  단일 행 SELECT 1건이라 60초 주기면 부하는 사실상 0.
    #  KIS 조회는 하지 않는다(라인은 메모리 값으로 재계산) → 장중에 돌아도 안전.
    def _poll_settings():
        now_kst = datetime.now(_KST)
        if now_kst.weekday() >= 5:
            return
        if not (_POLL_START_HOUR <= now_kst.hour < _POLL_END_HOUR):
            return
        if not _is_trading_day_cached(now_kst):
            return
        try:
            sell.apply_settings_change()
        except Exception as e:  # noqa: BLE001
            log.warning("[poll] 설정 반영 실패: %s", e)

    if cfg.settings_poll_sec > 0:
        scheduler.add_job(_poll_settings, IntervalTrigger(seconds=cfg.settings_poll_sec),
                          id="settings_poll", max_instances=1, coalesce=True)
        log.info("설정 변경 감지 등록: %d초마다", cfg.settings_poll_sec)
    else:
        log.info("설정 변경 감지 비활성 (SETTINGS_POLL_SEC=%d) → 변경은 재기동 후 반영",
                 cfg.settings_poll_sec)

    scheduler.start()
    for j in scheduler.get_jobs():
        log.info("스케줄러 job=%s · trigger=%s · 다음 실행=%s",
                 j.id, j.trigger, j.next_run_time)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    log.info("trade_worker 대기 (Ctrl+C 로 종료)")
    _stop.wait()

    scheduler.shutdown(wait=False)

    # 종료 직전 고점 flush — 배포·재시작이 장중에 일어나도 당일 고점을 잃지 않는다.
    try:
        sell.flush_peaks("종료")
    except Exception as e:  # noqa: BLE001
        log.warning("종료 시 고점 flush 실패: %s", e)

    log.info("trade_worker 종료")


if __name__ == "__main__":
    main()
