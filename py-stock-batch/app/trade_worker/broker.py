"""
Broker — pykis(PyKis) 주문/시세/실시간 소켓 + 체결 확인 래퍼.

실전투자 전용(모의투자 미지원).

체결 확인 전략:
  - 주력: **실시간 체결통보**(kis.on('execution'), H0STCNI0).
    주문번호별로 체결수량/체결가를 누적한다(부분체결 대응).
  - 보조: pending_orders() 폴링 fallback.
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
_KST = timezone("Asia/Seoul")


def _ono(order_number) -> Optional[str]:
    """KisOrderNumber → 주문번호 문자열 정규화."""
    if order_number is None:
        return None
    n = getattr(order_number, "number", None)
    return str(n) if n else str(order_number)


@dataclass
class OrderResult:
    symbol: str
    side: str                       # 'BUY' | 'SELL'
    qty: Decimal                    # 주문 수량
    price: Decimal                  # 참조가(주문 시점)
    order_no: Optional[str]
    dry_run: bool
    filled_qty: Decimal = field(default=Decimal(0))
    avg_price: Decimal = field(default=Decimal(0))
    status: str = "PENDING"         # FILLED|PARTIAL|REJECTED|PENDING
    reason: str = ""
    raw: object = None              # pykis KisOrder (취소용)


class Broker:
    def __init__(self, kis):
        self.kis = kis
        self.market = "KR"
        # 거래소 라우팅은 주문마다 종목 nxt_flag 기준으로 결정한다(_order → SOR/KRX).
        # self.exchange 는 하위호환용 기본값(현재 주문 경로에선 미사용).
        self.exchange = "SOR"
        # 주문번호 → 체결 누적 {exec_qty, amount(=Σqty*px), rejected, reason}
        self._fills: dict[str, dict] = {}
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
        bass = date or datetime.now(_KST).strftime("%Y%m%d")
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
        base = base or datetime.now(_KST).strftime("%Y%m%d")
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
    def orderable(self, symbol: str, price: Optional[Decimal] = None):
        """매수가능조회(inquire-psbl-order, TTTC8908R) → (qty:int, amount:Decimal) 또는 (None, None).

        KIS 공식 가이드 기준(미수 미사용):
          - 매수가능금액 = nrcvb_buy_amt(미수없는매수금액)   ※ ord_psbl_cash(주문가능현금)는 예수금 성격
          - 매수가능수량 = nrcvb_buy_qty(미수없는매수수량)
          - ORD_DVSN 은 반드시 01(시장가). 00(지정가)은 종목증거금율이 반영되지 않아 수량이 과다 계산됨.
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
                    "ORD_DVSN": "01",             # 01=시장가(종목증거금율 반영)
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
    def start_fill_tracking(self, on_event: Optional[Callable[[object], None]] = None):
        """실시간 체결통보 구독 시작. 주문번호별 체결 누적 + (선택) 외부 로깅 콜백."""
        def _cb(client, ev):
            try:
                self._apply_execution(ev.response)
                if on_event:
                    on_event(ev.response)
            except Exception as e:  # noqa: BLE001
                log.warning("체결통보 처리 실패: %s", e)

        try:
            # 체결통보는 account 객체의 on("execution", ...) 로 구독한다.
            # (PyKis 자체에는 on 이 없음)
            self._exec_ticket = self.kis.account().on("execution", _cb)
            log.info("실시간 체결통보 구독 시작")
        except Exception as e:  # noqa: BLE001
            log.warning("체결통보 구독 실패(폴링 fallback 사용): %s", e)

    def _apply_execution(self, execution):
        order_no = _ono(getattr(execution, "order_number", None))
        if not order_no:
            return
        eq = Decimal(str(getattr(execution, "executed_qty", 0) or 0))
        px = Decimal(str(getattr(execution, "price", 0) or 0))
        reason = getattr(execution, "rejected_reason", None)
        with self._lock:
            f = self._fills.setdefault(order_no, {"exec_qty": Decimal(0), "amount": Decimal(0),
                                                  "rejected": False, "reason": ""})
            f["exec_qty"] += eq
            f["amount"] += eq * px
            if reason:
                f["rejected"] = True
                f["reason"] = str(reason)

    def _fill_snapshot(self, order_no: str):
        with self._lock:
            f = self._fills.get(order_no)
            if not f:
                return None
            eq = f["exec_qty"]
            avg = (f["amount"] / eq) if eq > 0 else Decimal(0)
            return eq, avg, f["rejected"], f["reason"]

    # ── 주문 ────────────────────────────────────────────────────────
    def buy_market(self, symbol: str, qty: Decimal, ref_price: Decimal, nxt: bool = True) -> OrderResult:
        return self._order("BUY", symbol, qty, ref_price, nxt)

    def sell_market(self, symbol: str, qty: Decimal, ref_price: Decimal, nxt: bool = True) -> OrderResult:
        return self._order("SELL", symbol, qty, ref_price, nxt)

    def _order(self, side: str, symbol: str, qty: Decimal, ref_price: Decimal, nxt: bool = True) -> OrderResult:
        qty = Decimal(qty)

        # 거래소 라우팅: NXT 대상 → SOR(KRX+NXT 통합 최선체결), KRX 전용 → KRX.
        exchange = "SOR" if nxt else "KRX"
        order = self._order_rest(side, symbol, qty, exchange)
        order_no = _ono(getattr(order, "order_number", None) or order)
        log.info("[LIVE] %s 주문 접수 %s qty=%s order=%s exch=%s",
                 side, symbol, qty, order_no, exchange)
        return OrderResult(symbol, side, qty, Decimal(ref_price), order_no, False, raw=order)

    def _order_rest(self, side: str, symbol: str, qty: Decimal, exchange: str):
        """KIS REST order-cash 직접 호출 + EXCG_ID_DVSN_CD(KRX/NXT/SOR) 라우팅.
        pykis 의 인증/토큰/hashkey/도메인 파이프라인(kis.fetch)을 그대로 재사용하고,
        body 에 거래소 구분만 추가한다. 시장가(ORD_DVSN='01', ORD_UNPR='0'), 전량 qty."""
        from pykis.api.account.order import KisDomesticOrder, DOMESTIC_ORDER_API_CODES
        account = self.kis.primary  # KisAccountNumber (CANO/ACNT_PRDT_CD)
        return self.kis.fetch(
            "/uapi/domestic-stock/v1/trading/order-cash",
            api=DOMESTIC_ORDER_API_CODES[(True, side.lower())],  # 실전 TTTC0802U/0801U
            body={
                "PDNO": symbol,
                "ORD_DVSN": "01",              # 01=시장가
                "ORD_QTY": str(int(qty)),
                "ORD_UNPR": "0",
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
