"""
Broker — pykis(PyKis) 주문/시세/실시간 소켓 + 체결 확인 래퍼.

실전투자 전용(모의투자 미지원).

체결 확인 전략 (2단 구조):

  1) **동기 창** — wait_fill(). 주문 직후 정해진 시간 동안 체결을 확인한다.
     주문을 낸 executor 가 "지금 당장" 판단해야 하는 것(포지션 등록/청산)을 여기서 처리한다.

  2) **이벤트 드리븐** — register_watch() / arm_watch().
     동기 창이 닫힌 뒤 도착하는 체결통보를 콜백으로 흘려보낸다.
     지정가·부분체결처럼 창 안에 안 끝나는 주문의 잔량이 여기서 반영된다.
     ※ 전환 전에는 창 밖 체결통보가 _fills 에 쌓이기만 하고 아무도 읽지 않아,
       부분체결 잔량이 다음 부팅 대조 때까지 DB 와 어긋난 채로 남았다.

  보조: pending_orders() 폴링 fallback (소켓 유실 대비, 그대로 유지).

체결통보(H0STCNI0)는 **계좌 단위** 구독이라 worker 가 내지 않은 주문(HTS/MTS 등 타채널)의
체결도 들어온다. 이는 on_unknown 콜백으로 분리해 계좌 스냅샷 갱신에 쓴다.

동시성: 소켓 콜백은 별도 스레드에서 들어온다. _lock 은 누적/등록 상태 갱신만 감싸고,
콜백 호출(DB·KIS 접근)은 **반드시 락 밖에서** 한다.
"""
import logging
import threading
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, Optional

from pytz import timezone

log = logging.getLogger("trade_worker.broker")
TIMEZONE_KST = timezone("Asia/Seoul")


def _ono(order_number) -> Optional[str]:
    """KisOrderNumber → 주문번호 문자열 정규화."""
    if order_number is None:
        return None
    n = getattr(order_number, "number", None)
    return str(n) if n else str(order_number)


@dataclass(frozen=True)
class MarketSession:
    """지금 이 종목을 어느 거래소에 어떤 호가유형으로 낼 수 있는지."""
    tradable: bool
    exchange: str        # KRX / NXT / SOR
    ord_dvsn: str        # '01'=시장가 / '00'=지정가
    name: str            # 로그용 세션명

    @property
    def limit_only(self) -> bool:
        return self.ord_dvsn == "00"


@dataclass
class OrderResult:
    symbol: str
    side: str                       # 'BUY' | 'SELL'
    qty: Decimal                    # 주문 수량
    price: Decimal                  # 참조가(주문 시점)
    order_no: Optional[str]
    filled_qty: Decimal = field(default=Decimal(0))
    avg_price: Decimal = field(default=Decimal(0))
    status: str = "PENDING"         # FILLED|PARTIAL|REJECTED|PENDING
    reason: str = ""
    raw: object = None              # pykis KisOrder (취소용)


@dataclass
class FillEvent:
    """동기 창이 닫힌 뒤 도착한 체결통보 1건. delta_qty 가 이번에 **새로** 체결된 수량이다.

    executor 는 delta_qty 만 반영하면 된다. filled_qty(누적)로 반영하면 중복 계상된다.
    """
    order_no: str
    symbol: str
    side: str                       # 'BUY' | 'SELL'
    delta_qty: Decimal              # 이번 통보로 새로 체결된 수량 (반영 대상)
    filled_qty: Decimal             # 주문 개시 이후 누적 체결수량
    order_qty: Decimal              # 원 주문 수량
    avg_price: Decimal              # 누적 평균 체결가
    last_price: Decimal             # 이번 체결가
    complete: bool                  # filled_qty >= order_qty (전량 체결)
    rejected: bool = False
    reason: str = ""


@dataclass
class OrderWatch:
    """이벤트 드리븐 추적 대상 주문.

    armed=False 인 동안(=주문 직후 ~ executor 의 동기 처리 완료 전)에는 콜백하지 않는다.
    wait_fill 루프와 소켓 콜백이 같은 체결분을 동시에 반영해 이중 계상되는 것을 막기 위한
    유일한 장치다. executor 가 동기 처리를 끝내고 arm_watch() 를 부르면 그 시점의 체결수량이
    reported_qty 기준선이 되고, 이후 증분만 콜백된다.
    """
    order_no: str
    symbol: str
    side: str
    qty: Decimal                                  # 주문 수량
    on_fill: Callable[["FillEvent"], None]
    reported_qty: Decimal = field(default=Decimal(0))   # 콜백으로 이미 통지한 누적 수량
    armed: bool = False
    rejected_fired: bool = False
    created_at: float = field(default_factory=time.time)


class Broker:
    def __init__(self, kis):
        self.kis = kis
        self.market = "KR"
        # 거래소 라우팅은 주문마다 종목 nxt_flag 기준으로 결정한다(_order → SOR/KRX).
        # self.exchange 는 하위호환용 기본값(현재 주문 경로에선 미사용).
        self.exchange = "SOR"
        # 주문번호 → 체결 누적 {exec_qty, amount(=Σqty*px), rejected, reason, ts}
        self._fills: dict[str, dict] = {}
        # 주문번호 → OrderWatch. worker 가 낸 주문만 등록된다.
        self._watch: dict[str, OrderWatch] = {}
        # worker 가 내지 않은 주문(HTS/MTS 등)의 체결 콜백
        self._unknown_cb: Optional[Callable[[str, str, Decimal, Decimal], None]] = None
        self._lock = threading.Lock()
        self._exec_ticket = None

    # ── 시세 ────────────────────────────────────────────────────────
    def current_price(self, symbol: str, nxt: bool = True) -> Decimal:
        """현재가(체결가) 조회.
        nxt=True(NXT 대상): 통합(UN, KRX+NXT 최선호가) 우선 → 없으면 KRX(J) fallback.
        nxt=False(KRX 전용): 처음부터 KRX(J)만 조회.
        pykis quote()는 FID_COND_MRKT_DIV_CODE='J'(KRX 단독)로 하드코딩돼 있고,
        NXT 미대상 종목은 통합 시세가 없어 UN 이 비므로 J 로 재조회한다."""
        last = None
        markets = ("UN", "J") if nxt else ("J",)  # UN: 통합(KRX+NXT), J: KRX 단독
        for mkt in markets:
            resp = self.kis.request(
                "/uapi/domestic-stock/v1/quotations/inquire-price",
                method="GET",
                params={"FID_COND_MRKT_DIV_CODE": mkt, "FID_INPUT_ISCD": symbol},
                headers={"tr_id": "FHKST01010100", "custtype": "P"},
                appkey_location="header", auth=True,
            )
            j = resp.json()
            last = j
            prpr = (j.get("output") or {}).get("stck_prpr") if j.get("rt_cd") == "0" else None
            if prpr:
                return Decimal(str(prpr))
        raise RuntimeError(
            f"현재가 조회 실패 {symbol}: rt_cd={(last or {}).get('rt_cd')} msg={(last or {}).get('msg1')}")

    # ── 개장(휴장일) 확인 ───────────────────────────────────────────
    def is_trading_day(self, date: Optional[str] = None) -> Optional[bool]:
        """오늘(또는 지정일 YYYYMMDD)이 국내 개장일인지 KIS 국내휴장일조회로 확인.
        반환: True=개장일 / False=휴장일 / None=조회 실패(호출측 판단).
        (chk-holiday, TR CTCA0903R). output 각 행의 opnd_yn(개장일여부) 기준."""
        bass = date or datetime.now(TIMEZONE_KST).strftime("%Y%m%d")
        rows = self._holiday_rows(bass)
        if rows is None:
            return None
        for row in rows:
            if row.get("bass_dt") == bass:
                return row.get("opnd_yn") == "Y"
        return None

    def prev_trading_day(self, base: Optional[str] = None, lookback_days: int = 15) -> Optional[str]:
        """base(YYYYMMDD, 기본 KST 오늘) 직전 영업일(개장일)을 KIS 휴장일조회로 동적 산출.
        base-lookback_days 부터 1회 조회해 opnd_yn=='Y' 이면서 base 이전인 날짜 중 최대.
        반환: 직전 개장일 YYYYMMDD / None(조회 실패). 15일이면 연휴(설·추석)도 커버."""
        base = base or datetime.now(TIMEZONE_KST).strftime("%Y%m%d")
        start = (datetime.strptime(base, "%Y%m%d") - timedelta(days=lookback_days)).strftime("%Y%m%d")
        rows = self._holiday_rows(start)
        if rows is None:
            return None
        opened = [r["bass_dt"] for r in rows
                  if r.get("opnd_yn") == "Y" and r.get("bass_dt") and r["bass_dt"] < base]
        return max(opened) if opened else None

    def _holiday_rows(self, bass_dt: str) -> Optional[list]:
        """국내휴장일조회(chk-holiday, CTCA0903R) → bass_dt 부터의 날짜별 플래그 rows.
        실패 시 None. (개장/휴장 판정·직전 영업일 산출 공용)"""
        try:
            resp = self.kis.request(
                "/uapi/domestic-stock/v1/quotations/chk-holiday",
                method="GET",
                params={"BASS_DT": bass_dt, "CTX_AREA_NK": "", "CTX_AREA_FK": ""},
                headers={"tr_id": "CTCA0903R", "custtype": "P"},
                appkey_location="header", auth=True,
            )
            j = resp.json()
            if j.get("rt_cd") != "0":
                log.warning("휴장일조회 실패 rt_cd=%s msg=%s", j.get("rt_cd"), j.get("msg1"))
                return None
            return j.get("output") or []
        except Exception as e:  # noqa: BLE001
            log.warning("휴장일조회 예외 %s: %s", bass_dt, e)
            return None

    # ── 매수가능조회 (주문가능금액·주문가능수량) ────────────────────
    def orderable(self, symbol: str, price: Optional[Decimal] = None, ord_dvsn: str = "01"):
        """매수가능조회(inquire-psbl-order, TTTC8908R) → (qty:int, amount:Decimal) 또는 (None, None).

        KIS 공식 가이드 기준(미수 미사용):
          - 매수가능금액 = nrcvb_buy_amt(미수없는매수금액)   ※ ord_psbl_cash(주문가능현금)는 예수금 성격
          - 매수가능수량 = nrcvb_buy_qty(미수없는매수수량)
          - ORD_DVSN 은 기본 01(시장가). 00(지정가)은 종목증거금율이 반영되지 않아 수량이 과다 계산되므로
            정규장에서는 반드시 01 을 쓴다. NXT 프리마켓처럼 지정가만 허용되는 세션에 한해
            ord_dvsn='00' + 실제 지정가(price)를 넘겨 그 가격 기준 수량을 받는다.
        pykis 의 orderable_amount() 는 amount=ord_psbl_cash / qty=max_buy_qty(미수 사용) 로
        매핑돼 있어 직접 REST 를 호출한다."""
        try:
            account = self.kis.primary  # KisAccountNumber (CANO/ACNT_PRDT_CD)
            resp = self.kis.request(
                "/uapi/domestic-stock/v1/trading/inquire-psbl-order",
                method="GET",
                params={
                    "CANO": account.number,
                    "ACNT_PRDT_CD": account.code,
                    "PDNO": symbol,
                    "ORD_UNPR": str(int(price)) if price else "0",
                    "ORD_DVSN": ord_dvsn,         # 01=시장가(종목증거금율 반영) / 00=지정가
                    "CMA_EVLU_AMT_ICLD_YN": "N",  # CMA평가금액 미포함
                    "OVRS_ICLD_YN": "N",          # 해외 미포함
                },
                headers={"tr_id": "TTTC8908R", "custtype": "P"},
                appkey_location="header", auth=True,
            )
            j = resp.json()
            if j.get("rt_cd") != "0":
                log.warning("매수가능조회 실패 %s: rt_cd=%s msg=%s",
                            symbol, j.get("rt_cd"), j.get("msg1"))
                return None, None
            o = j.get("output") or {}
            amount = Decimal(str(o.get("nrcvb_buy_amt") or 0))   # 미수없는매수금액
            qty = int(Decimal(str(o.get("nrcvb_buy_qty") or 0)))  # 미수없는매수수량
            return qty, amount
        except Exception as e:  # noqa: BLE001
            log.warning("매수가능조회 실패 %s: %s", symbol, e)
            return None, None

    # ── 실제 매수가능금액 조회 ──────────────────────────────────────
    # 매수가능조회 레퍼런스 종목. 매수가능금액(nrcvb_buy_amt)은 계좌 단위 값이라
    # 종목과 무관하지만 API 는 PDNO 가 필수 → 고정 대형주(삼성전자)로 조회한다.
    CASH_REF_SYMBOL = "005930"

    def account_cash(self) -> Optional[Decimal]:
        """실제 '매수가능금액'(nrcvb_buy_amt, 미수없는매수금액) 조회. 실패 시 None.
        예수금총액(dnca_tot_amt)·주문가능현금(ord_psbl_cash)이 아니라
        증거금율까지 반영된 지금 실제로 주문 가능한 금액이다.
        (currency 인자는 하위호환용; 국내 KRW 계좌만 지원)"""
        _, amount = self.orderable(self.CASH_REF_SYMBOL)
        return amount

    # ── 실제 보유 종목 조회 ──────────────────────────────────────────
    def account_holdings(self) -> Optional[list]:
        """KIS 계좌의 실제 보유 종목 리스트. 실패 시 None.
        각 항목: symbol, name, qty, avg_price, cur_price, eval_amount, profit."""
        try:
            balance = self.kis.account().balance()
            out = []
            for st in balance.stocks:
                market = getattr(st, "market", "KRX")
                if market and market != "KRX":
                    continue  # 국내(KRX) 보유만
                qty = Decimal(str(getattr(st, "qty", 0) or 0))
                if qty <= 0:
                    continue
                pur = Decimal(str(getattr(st, "purchase_amount", 0) or 0))
                out.append({
                    "symbol": getattr(st, "symbol", "") or "",
                    "name": getattr(st, "name", "") or "",
                    "qty": qty,
                    "avg_price": (pur / qty) if qty > 0 else Decimal(0),
                    "cur_price": Decimal(str(getattr(st, "price", 0) or 0)),
                    "eval_amount": Decimal(str(getattr(st, "amount", 0) or 0)),
                    "profit": Decimal(str(getattr(st, "profit", 0) or 0)),
                })
            return out
        except Exception as e:  # noqa: BLE001
            log.warning("계좌 보유종목 조회 실패: %s", e)
            return None

    # ── 체결통보 구독 (fill tracking) ────────────────────────────────
    def start_fill_tracking(self, on_event: Optional[Callable[[object], None]] = None,
                            on_unknown: Optional[Callable[[str, str, Decimal, Decimal], None]] = None):
        """실시간 체결통보 구독 시작.

        on_event   : 원본 통보 로깅 훅(모든 통보).
        on_unknown : worker 가 내지 않은 주문(HTS/MTS 등 타채널)의 체결 콜백.
                     (symbol, order_no, qty, price) 로 호출된다.
                     계좌 스냅샷(user_wallet·user_holdings)을 즉시 갱신하는 데 쓴다.
                     ※ 통보가 연달아 오므로 호출측에서 throttle 할 것.
        """
        self._unknown_cb = on_unknown

        def _cb(client, ev):
            try:
                self._apply_execution(ev.response)
            except Exception as e:  # noqa: BLE001
                log.warning("체결통보 처리 실패: %s", e)
            # 로깅 훅은 누적/디스패치 실패와 무관하게 항상 시도한다.
            if on_event:
                try:
                    on_event(ev.response)
                except Exception as e:  # noqa: BLE001
                    log.warning("체결통보 로깅 훅 실패: %s", e)

        try:
            # 체결통보는 account 객체의 on("execution", ...) 로 구독한다.
            # (PyKis 자체에는 on 이 없음)
            self._exec_ticket = self.kis.account().on("execution", _cb)
            log.info("실시간 체결통보 구독 시작 (이벤트 드리븐)")
        except Exception as e:  # noqa: BLE001
            log.warning("체결통보 구독 실패(폴링 fallback 사용): %s", e)

    # ── 주문 추적 등록/해제 ──────────────────────────────────────────
    def register_watch(self, result: OrderResult, on_fill: Callable[[FillEvent], None]) -> None:
        """주문 직후 호출. 이 주문의 체결통보를 추적 대상에 넣는다.

        아직 armed=False 라 콜백은 나가지 않는다. wait_fill 로 동기 처리를 끝낸 뒤
        arm_watch() 를 불러야 이후 증분이 콜백된다.
        """
        if not result.order_no:
            return
        with self._lock:
            self._watch[result.order_no] = OrderWatch(
                order_no=result.order_no, symbol=result.symbol, side=result.side,
                qty=result.qty, on_fill=on_fill,
            )

    def arm_watch(self, result: OrderResult) -> bool:
        """동기 처리 완료 선언. result.filled_qty 를 기준선으로 삼고 이후 증분만 콜백한다.

        반환: True=추적 계속(잔량 있음) / False=추적 종료(전량 체결·거부·미등록).
        """
        if not result.order_no:
            return False
        with self._lock:
            w = self._watch.get(result.order_no)
            if w is None:
                return False
            w.reported_qty = result.filled_qty
            w.armed = True
            done = (result.filled_qty >= w.qty) or result.status == "REJECTED"
            if done:
                self._watch.pop(result.order_no, None)
        if done:
            return False
        log.info("체결추적 시작 %s %s order=%s 잔량=%s",
                 result.side, result.symbol, result.order_no, result.qty - result.filled_qty)
        return True

    def unregister_watch(self, order_no: Optional[str]) -> None:
        """추적 종료(주문 취소·정리)."""
        if not order_no:
            return
        with self._lock:
            self._watch.pop(order_no, None)

    def sweep_watches(self, max_age_sec: int = 21600) -> None:
        """오래된 추적/누적을 정리한다(메모리 누수 방지). 기본 6시간.

        정상 경로에서는 전량 체결·거부·취소 시 해제되지만, 끝내 체결도 취소도 되지 않은
        주문이 남을 수 있다. 폴링 job 에서 주기적으로 부른다.
        """
        now = time.time()
        stale = []
        with self._lock:
            for ono, w in list(self._watch.items()):
                if now - w.created_at > max_age_sec:
                    stale.append((ono, w.symbol, w.side, w.reported_qty, w.qty))
                    self._watch.pop(ono, None)
            for ono, f in list(self._fills.items()):
                if ono not in self._watch and now - f.get("ts", now) > max_age_sec:
                    self._fills.pop(ono, None)
        for ono, sym, side, rq, q in stale:
            log.warning("체결추적 만료 해제 %s %s order=%s (%s/%s) — 수동 확인 필요",
                        side, sym, ono, rq, q)

    # ── 체결통보 수신 → 누적 → 디스패치 ─────────────────────────────
    def _apply_execution(self, execution):
        order_no = _ono(getattr(execution, "order_number", None))
        if not order_no:
            return
        eq = Decimal(str(getattr(execution, "executed_qty", 0) or 0))
        px = Decimal(str(getattr(execution, "price", 0) or 0))
        reason = getattr(execution, "rejected_reason", None)
        symbol = str(getattr(execution, "symbol", "") or "")

        watch, event, unknown = None, None, False
        with self._lock:
            f = self._fills.setdefault(order_no, {"exec_qty": Decimal(0), "amount": Decimal(0),
                                                  "rejected": False, "reason": "", "ts": 0.0})
            f["exec_qty"] += eq
            f["amount"] += eq * px
            f["ts"] = time.time()
            if reason:
                f["rejected"] = True
                f["reason"] = str(reason)

            w = self._watch.get(order_no)
            if w is None:
                # worker 가 낸 주문이 아니다 = 타채널(HTS/MTS) 또는 이미 추적 종료된 주문.
                unknown = True
            elif w.armed:
                event = self._build_event(w, f, px, symbol)
                if event is not None and (event.complete or event.rejected):
                    self._watch.pop(order_no, None)
                watch = w

        # ── 락 밖: 콜백은 DB/KIS 를 만지므로 절대 락 안에서 부르지 않는다 ──
        if unknown:
            if self._unknown_cb:
                try:
                    self._unknown_cb(symbol, order_no, eq, px)
                except Exception as e:  # noqa: BLE001
                    log.warning("외부주문 체결 콜백 실패 %s: %s", order_no, e)
            return
        if event is not None and watch is not None:
            try:
                watch.on_fill(event)
            except Exception as e:  # noqa: BLE001
                log.warning("체결 콜백 실패 %s %s order=%s: %s",
                            event.side, event.symbol, order_no, e)

    def _build_event(self, w: OrderWatch, f: dict, last_px: Decimal, symbol: str):
        """누적 상태에서 '아직 통지하지 않은 증분'을 뽑아 FillEvent 를 만든다. (락 안에서 호출)

        증분이 없고 거부도 아니면 None — 같은 체결을 두 번 반영하지 않기 위함이다.
        """
        eq = f["exec_qty"]
        rejected = bool(f["rejected"])
        delta = eq - w.reported_qty
        if delta <= 0 and not (rejected and not w.rejected_fired):
            return None
        w.reported_qty = eq
        if rejected:
            w.rejected_fired = True
        avg = (f["amount"] / eq) if eq > 0 else Decimal(0)
        return FillEvent(
            order_no=w.order_no, symbol=w.symbol or symbol, side=w.side,
            delta_qty=delta if delta > 0 else Decimal(0),
            filled_qty=eq, order_qty=w.qty, avg_price=avg, last_price=last_px,
            complete=(eq >= w.qty), rejected=rejected, reason=f["reason"],
        )

    def _fill_snapshot(self, order_no: str):
        with self._lock:
            f = self._fills.get(order_no)
            if not f:
                return None
            eq = f["exec_qty"]
            avg = (f["amount"] / eq) if eq > 0 else Decimal(0)
            return eq, avg, f["rejected"], f["reason"]

    # ── 거래 세션 판정 (NXT / KRX 분리) ─────────────────────────────
    #   KRX  : 09:00~15:30 정규장(시장가 가능)
    #   NXT  : 프리마켓 08:00~08:50 · 메인 09:00~15:20 · 애프터마켓 15:30~20:00
    #          프리/애프터마켓은 **지정가 호가만** 허용 → ORD_DVSN='00', 거래소 'NXT' 고정.
    #          (이 시간대 KRX 는 닫혀 있어 SOR 통합 라우팅이 성립하지 않는다)
    #   메인 세션은 SOR(KRX+NXT 통합 최선체결) 로 시장가.
    #   NXT 메인은 15:20 에 끝나므로 15:20~15:30 은 KRX 단독 시장가로 넘긴다.
    @staticmethod
    def market_session(nxt: bool, now: Optional[datetime] = None) -> "MarketSession":
        """(nxt_flag 기준) 지금 이 종목을 주문할 수 있는 세션. 불가면 tradable=False."""
        now = now or datetime.now(TIMEZONE_KST)
        if now.weekday() >= 5:
            return MarketSession(False, "", "", "주말")
        hm = now.hour * 60 + now.minute

        if nxt and 8 * 60 <= hm < 8 * 60 + 50:
            return MarketSession(True, "NXT", "00", "NXT프리마켓")
        if 9 * 60 <= hm < 15 * 60 + 20:
            return MarketSession(True, "SOR" if nxt else "KRX", "01", "정규장")
        if 15 * 60 + 20 <= hm < 15 * 60 + 30:
            # NXT 메인 종료, KRX 만 열려 있음
            return MarketSession(True, "KRX", "01", "정규장(KRX단독)")
        if nxt and 15 * 60 + 30 <= hm < 20 * 60:
            return MarketSession(True, "NXT", "00", "NXT애프터마켓")
        return MarketSession(False, "", "", "장운영시간외")

    # ── 호가단위 ────────────────────────────────────────────────────
    # 2023.1 호가가격단위 개편 기준(유가증권·코스닥 동일 7단계).
    # 지정가 주문은 호가단위에 맞지 않으면 거부되므로 반드시 정렬해서 보낸다.
    _TICKS = ((2_000, 1), (5_000, 5), (20_000, 10), (50_000, 50),
              (200_000, 100), (500_000, 500))

    @classmethod
    def tick_size(cls, price: Decimal) -> int:
        for upper, tick in cls._TICKS:
            if price < upper:
                return tick
        return 1_000

    @classmethod
    def align_price(cls, price: Decimal) -> Decimal:
        """지정가를 호가단위로 내림 정렬. 매수 지정가는 내림이 안전
        (올림하면 상한가를 넘겨 거부될 수 있다)."""
        price = Decimal(price)
        tick = Decimal(cls.tick_size(price))
        return (price // tick) * tick

    # ── 주문 ────────────────────────────────────────────────────────
    def buy_market(self, symbol: str, qty: Decimal, ref_price: Decimal, nxt: bool = True) -> OrderResult:
        return self._order("BUY", symbol, qty, ref_price, nxt)

    def sell_market(self, symbol: str, qty: Decimal, ref_price: Decimal, nxt: bool = True) -> OrderResult:
        return self._order("SELL", symbol, qty, ref_price, nxt)

    def order_in_session(self, side: str, symbol: str, qty: Decimal,
                         ref_price: Decimal, sess: MarketSession) -> OrderResult:
        """세션(MarketSession)이 정해준 거래소·호가유형으로 주문.

        지정가 세션(NXT 프리/애프터마켓)이면 ref_price 를 호가단위로 정렬해 그대로 지정가로 낸다.
        호출측이 이미 슬리피지를 반영한 가격을 넘겨준다(매수=위로, 매도=아래로).
        """
        qty = Decimal(qty)
        px = self.align_price(ref_price) if sess.limit_only else Decimal(0)
        order = self._order_rest(side, symbol, qty, sess.exchange,
                                 ord_dvsn=sess.ord_dvsn, ord_unpr=px)
        order_no = _ono(getattr(order, "order_number", None) or order)
        log.info("[LIVE] %s 주문 접수 %s qty=%s %s=%s order=%s exch=%s (%s)",
                 side, symbol, qty,
                 "지정가" if sess.limit_only else "시장가",
                 px if sess.limit_only else "-",
                 order_no, sess.exchange, sess.name)
        return OrderResult(symbol, side, qty,
                           px if sess.limit_only else Decimal(ref_price),
                           order_no, raw=order)

    def buy_limit_nxt(self, symbol: str, qty: Decimal, limit_price: Decimal) -> OrderResult:
        """NXT 프리마켓(08:00~08:50) 전용 지정가 매수. order_in_session 의 얇은 래퍼."""
        return self.order_in_session("BUY", symbol, qty, limit_price,
                                     MarketSession(True, "NXT", "00", "NXT프리마켓"))

    def _order(self, side: str, symbol: str, qty: Decimal, ref_price: Decimal, nxt: bool = True) -> OrderResult:
        qty = Decimal(qty)

        # 거래소 라우팅: NXT 대상 → SOR(KRX+NXT 통합 최선체결), KRX 전용 → KRX.
        exchange = "SOR" if nxt else "KRX"
        order = self._order_rest(side, symbol, qty, exchange)
        order_no = _ono(getattr(order, "order_number", None) or order)
        log.info("[LIVE] %s 주문 접수 %s qty=%s order=%s exch=%s",
                 side, symbol, qty, order_no, exchange)
        return OrderResult(symbol, side, qty, Decimal(ref_price), order_no, raw=order)

    def _order_rest(self, side: str, symbol: str, qty: Decimal, exchange: str,
                    ord_dvsn: str = "01", ord_unpr: Decimal | int = 0):
        """KIS REST order-cash 직접 호출 + EXCG_ID_DVSN_CD(KRX/NXT/SOR) 라우팅.
        pykis 의 인증/토큰/hashkey/도메인 파이프라인(kis.fetch)을 그대로 재사용하고,
        body 에 거래소 구분만 추가한다.
        기본 시장가(ORD_DVSN='01', ORD_UNPR='0'), 지정가는 '00' + 실제 가격."""
        from pykis.api.account.order import KisDomesticOrder, DOMESTIC_ORDER_API_CODES
        account = self.kis.primary  # KisAccountNumber (CANO/ACNT_PRDT_CD)
        return self.kis.fetch(
            "/uapi/domestic-stock/v1/trading/order-cash",
            api=DOMESTIC_ORDER_API_CODES[(True, side.lower())],  # 실전 TTTC0802U/0801U
            body={
                "PDNO": symbol,
                "ORD_DVSN": ord_dvsn,          # 01=시장가 / 00=지정가
                "ORD_QTY": str(int(qty)),
                "ORD_UNPR": str(int(ord_unpr)),
                "EXCG_ID_DVSN_CD": exchange,   # KRX / NXT / SOR
            },
            form=[account],
            response_type=KisDomesticOrder(account_number=account, symbol=symbol, market="KRX"),
            method="POST",
        )

    def cancel(self, result: OrderResult) -> bool:
        """미체결 주문 취소(best-effort). 성공 True."""
        if result.raw is None:
            return False
        try:
            self.kis.account().cancel(order=result.raw)
            log.info("주문 취소 요청 %s order=%s", result.symbol, result.order_no)
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("주문 취소 실패 %s order=%s: %s", result.symbol, result.order_no, e)
            return False

    # ── 체결 확인 ────────────────────────────────────────────────────
    def wait_fill(self, result: OrderResult, timeout: float = 10.0, poll: float = 0.5) -> OrderResult:
        """접수 → 체결 확인. 실시간 체결통보 누적을 우선 사용, 실전은 pending 폴링 보조."""

        if not result.order_no:
            result.status = "PENDING"
            result.reason = "주문번호 없음"
            return result

        deadline = time.time() + timeout
        while time.time() < deadline:
            snap = self._fill_snapshot(result.order_no)
            if snap:
                eq, avg, rejected, reason = snap
                if rejected:
                    result.status, result.reason = "REJECTED", reason
                    result.filled_qty, result.avg_price = eq, avg
                    return result
                if eq >= result.qty:
                    result.status = "FILLED"
                    result.filled_qty, result.avg_price = eq, (avg or result.price)
                    return result
                result.filled_qty, result.avg_price = eq, (avg or result.price)  # 부분체결 진행중

            # 보조 폴링: 미체결 목록에서 사라지면 전량 체결로 간주
            if self._not_in_pending(result.order_no):
                # 미체결 목록에 없음 = 전량 체결(또는 취소)로 간주
                if result.filled_qty <= 0:
                    result.filled_qty, result.avg_price = result.qty, result.price
                result.status = "FILLED"
                return result

            time.sleep(poll)

        # 타임아웃
        result.status = "PARTIAL" if result.filled_qty > 0 else "PENDING"
        if not result.reason:
            result.reason = f"체결확인 타임아웃({timeout}s)"
        return result

    def _not_in_pending(self, order_no: str) -> bool:
        try:
            acct = self.kis.account()
            pend = acct.pending_orders()
            return not any(_ono(o.order_number) == order_no for o in pend.orders)
        except Exception as e:  # noqa: BLE001
            log.debug("pending_orders 조회 실패(무시): %s", e)
            return False

    # ── 실시간 시세 구독 ─────────────────────────────────────────────
    def subscribe_price(self, symbol: str, callback: Callable[[str, Decimal], None], nxt: bool = True):
        """실시간 체결가 구독 — NXT 대상은 통합(H0UNCNT0), KRX 전용은 KRX(H0STCNT0).
        pykis stock.on('price')는 H0STCNT0(KRX 단독)로 하드코딩돼 있어 TR을 직접 지정한다.
        통합 실시간체결가(H0UNCNT0)의 payload 필드 레이아웃은 H0STCNT0과 동일하므로
        KisDomesticRealtimePrice 파서를 그대로 재사용한다.
        ※ NXT 대상 여부(nxt)는 master_stock.nxt_flag 기준. KRX 전용은 통합 스트림이 없으므로 KRX(H0STCNT0)로 구독한다."""
        from pykis.api.websocket import WEBSOCKET_RESPONSES_MAP
        from pykis.api.websocket.price import KisDomesticRealtimePrice
        from pykis.event.filters.product import KisProductEventFilter

        # 통합 실시간체결가 TR을 파서 레지스트리에 등록(멱등). H0STCNT0과 동일 스펙.
        WEBSOCKET_RESPONSES_MAP.setdefault("H0UNCNT0", KisDomesticRealtimePrice)

        tr_id = "H0UNCNT0" if nxt else "H0STCNT0"
        log.info("실시간 체결가 구독 %s TR=%s", symbol, tr_id)

        def _cb(client, ev):
            try:
                callback(symbol, Decimal(str(ev.response.price)))
            except Exception as e:  # noqa: BLE001
                log.warning("price 콜백 실패 %s: %s", symbol, e)

        # symbol 단위로 필터링(다른 종목의 이벤트 유입 차단)
        where = KisProductEventFilter(symbol=symbol, market="KRX")
        return self.kis.websocket.on(
            id=tr_id, key=symbol, callback=_cb, where=where,
        )
