"""
수동 매수 단위 검증 — DB / KIS 불필요(가짜 객체). 실제 주문은 나가지 않는다.

무엇을 검증하나
    1. resolve_session — 시장가는 정규장만, 지정가는 프리·애프터마켓 포함
    2. next_state      — 체결/취소/거부/날짜 경과/조회 실패 판정
    3. _parse_order_status — 주문번호 앞자리 0 차이, 없는 주문
    4. Broker 게이트   — M0 에서 일반 매수는 막히고 manual_buy 만 나간다
    5. 실행기 흐름     — 한 번만 주문, 수량 초과 거부, 거래소 거부, 결과 불명(재주문 안 함),
                         휴장일, 체결 후처리 1회, 취소

실행
    poetry run python -m app.test.test_manual_buy_unit
"""
import sys
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from pykis.client.exceptions import KisAPIError
from pytz import timezone

from app.trade_worker import manual_buy as MB
from app.trade_worker.broker import Broker, MarketSession, OrderResult, TradingHaltedError
from app.trade_worker.manual_buy import ManualBuyExecutor, next_state, qty_from_pct, resolve_session

PASS, FAIL = [], []
KST = timezone("Asia/Seoul")
TUE = dict(year=2026, month=11, day=3)


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('  PASS ' if cond else '  FAIL ') + name + (f'  -- {detail}' if detail and not cond else ''))


def at(h, m):
    return KST.localize(datetime(hour=h, minute=m, **TUE))


# ── 1 ─────────────────────────────────────────────────────────────────────
def test_session():
    print('\n[1] resolve_session')
    s, _ = resolve_session('MARKET', True, True, at(10, 0))
    check('시장가 10:00 NXT → SOR 시장가', s and s.exchange == 'SOR' and s.ord_dvsn == '01')
    s, _ = resolve_session('MARKET', False, True, at(10, 0))
    check('시장가 10:00 KRX → KRX 시장가', s and s.exchange == 'KRX' and s.ord_dvsn == '01')
    s, why = resolve_session('MARKET', True, True, at(8, 10))
    check('시장가 프리마켓 거부', s is None and '정규장' in why)
    s, why = resolve_session('MARKET', False, True, at(16, 30))
    check('시장가 애프터마켓 거부', s is None and '정규장' in why)
    s, _ = resolve_session('LIMIT', True, True, at(10, 0))
    check('지정가 정규장 → ORD_DVSN 00', s and s.ord_dvsn == '00' and s.exchange == 'SOR' and s.limit_only)
    s, _ = resolve_session('LIMIT', True, True, at(8, 10))
    check('지정가 NXT 프리마켓 허용', s and s.exchange == 'NXT' and s.ord_dvsn == '00')
    s, _ = resolve_session('LIMIT', False, True, at(8, 10))
    check('지정가 KRX 전용 프리마켓 거부', s is None)
    s, _ = resolve_session('LIMIT', False, True, at(16, 30))
    check('지정가 KRX 애프터마켓 → 41', s and s.ord_dvsn == '41')
    s, _ = resolve_session('LIMIT', False, False, at(16, 30))
    check('KRX 애프터마켓 꺼짐 → 거부', s is None)
    s, _ = resolve_session('LIMIT', True, True, at(21, 0))
    check('21:00 지정가 거부', s is None)


# ── 2 ─────────────────────────────────────────────────────────────────────
def S(filled, remain, rejected=0):
    return {'found': True, 'filled_qty': Decimal(filled), 'avg_price': Decimal(1000),
            'remain_qty': Decimal(remain), 'rejected_qty': Decimal(rejected)}


def test_next_state():
    print('\n[2] next_state')
    d, nd = '20261103', '20261104'
    check('전량 체결', next_state(10, S(10, 0), d, d) == 'FILLED')
    check('미체결 진행 중', next_state(10, S(0, 10), d, d) is None)
    check('부분체결 진행 중', next_state(10, S(4, 6), d, d) is None)
    check('전량 취소', next_state(10, S(0, 0), d, d) == 'CANCELLED')
    check('부분체결 후 취소', next_state(10, S(4, 0), d, d) == 'CANCELLED')
    check('거래소 거부', next_state(10, S(0, 0, 10), d, d) == 'REJECTED')
    check('조회 실패 → 판단 보류', next_state(10, None, d, d) is None)
    check('날짜 경과해도 조회 실패면 보류', next_state(10, None, d, nd) is None)
    check('목록에 아직 없음 → 대기', next_state(10, {'found': False}, d, d) is None)
    check('다음 날 잔량 → 만료', next_state(10, S(4, 6), d, nd) == 'EXPIRED')
    check('다음 날 목록에 없음 → 만료', next_state(10, {'found': False}, d, nd) == 'EXPIRED')


# ── 3 ─────────────────────────────────────────────────────────────────────
def test_parse():
    print('\n[3] _parse_order_status')
    rows = [{'odno': '0000099', 'tot_ccld_qty': '1', 'avg_prvs': '1', 'rmn_qty': '0', 'rjct_qty': '0'},
            {'odno': '0000123', 'tot_ccld_qty': '3', 'avg_prvs': '1500.5', 'rmn_qty': '7', 'rjct_qty': '0'}]
    st = Broker._parse_order_status(rows, '123')
    check('앞자리 0 무시하고 매칭', st['found'] and st['filled_qty'] == 3 and st['remain_qty'] == 7)
    check('평균가 파싱', st['avg_price'] == Decimal('1500.5'))
    check('없는 주문', Broker._parse_order_status(rows, '555') == {'found': False})
    check('빈 목록', Broker._parse_order_status([], '123') == {'found': False})


# ── 4 ─────────────────────────────────────────────────────────────────────
class FakeKis:
    virtual = False
    primary = SimpleNamespace(number='1', code='01')

    def __init__(self):
        self.bodies = []

    def fetch(self, path, api=None, body=None, form=None, response_type=None, method=None):
        self.bodies.append(body)
        return SimpleNamespace(order_number=SimpleNamespace(number='777'), branch='06010')


def test_gate():
    print('\n[4] Broker 매매정지 게이트')
    kis = FakeKis()
    b = Broker(kis)
    b.set_trading_gate(lambda side: side != 'BUY')   # M0
    try:
        b.buy_market('005930', Decimal(1), Decimal(1000))
        check('M0: 일반 매수 차단', False)
    except TradingHaltedError:
        check('M0: 일반 매수 차단', True)
    check('M0: 일반 매수는 주문 안 나감', kis.bodies == [])

    res = b.manual_buy('005930', Decimal(3), MarketSession(True, 'SOR', '01', '정규장'))
    check('M0: 수동 시장가는 나감', res.order_no == '777' and kis.bodies[-1]['ORD_DVSN'] == '01')
    check('시장가 단가 0', kis.bodies[-1]['ORD_UNPR'] == '0' and kis.bodies[-1]['ORD_QTY'] == '3')
    res = b.manual_buy('005930', Decimal(2), MarketSession(True, 'SOR', '00', '정규장'), Decimal('70000'))
    check('수동 지정가 단가 전달', kis.bodies[-1]['ORD_UNPR'] == '70000' and kis.bodies[-1]['ORD_DVSN'] == '00')
    check('취소용 값 보관', res.branch == '06010' and res.exchange == 'SOR' and res.ord_dvsn == '00')


# ── 5 ─────────────────────────────────────────────────────────────────────
class FakeRepo:
    """상태 전이 조건까지 메모리에서 흉내 낸다."""

    def __init__(self, rows=()):
        self.rows = {r['id']: r for r in rows}
        self.trade_logs = []
        self.logs = []

    def insert_worker_log(self, *a, **k):
        self.logs.append(a)

    def expire_stale_manual_buys(self, uid, ttl):
        pass

    def get_requested_manual_buys(self, uid):
        return [dict(r) for r in self.rows.values() if r['state'] == 'REQUESTED']

    def get_open_manual_buys(self, uid):
        return [dict(r) for r in self.rows.values() if r['state'] == 'OPEN']

    def claim_manual_buy(self, uid, id_):
        r = self.rows[id_]
        if r['state'] != 'REQUESTED':
            return False
        r['state'] = 'ORDERING'
        return True

    def set_manual_buy_qty(self, uid, id_, qty):
        self.rows[id_]['qty'] = qty

    def mark_manual_buy_open(self, uid, id_, no, branch, dvsn, exch, sess, ymd):
        self.rows[id_].update(state='OPEN', order_no=no, branch=branch, ord_dvsn=dvsn,
                              exchange=exch, session_name=sess, order_ymd=ymd)

    def finish_manual_buy(self, uid, id_, from_state, state, reason=None, filled_qty=None, avg_price=None):
        r = self.rows[id_]
        if r['state'] != from_state:
            return False
        r['state'] = state
        if reason:
            r['reason'] = reason
        if filled_qty is not None:
            r['filled_qty'] = filled_qty
        if avg_price:
            r['avg_fill_price'] = avg_price
        r['cancel_requested'] = 'N'
        return True

    def update_manual_buy_fill(self, uid, id_, qty, avg):
        self.rows[id_].update(filled_qty=qty, avg_fill_price=avg)

    def clear_manual_buy_cancel(self, uid, id_, reason):
        self.rows[id_]['cancel_requested'] = 'N'
        if reason:
            self.rows[id_]['reason'] = reason

    def mark_ordering_manual_buys_unknown(self, uid, reason):
        n = 0
        for r in self.rows.values():
            if r['state'] == 'ORDERING':
                r.update(state='UNKNOWN', reason=reason)
                n += 1
        return n

    def insert_trade_log(self, uid, code, action, px, qty, bal, note=''):
        self.trade_logs.append((code, action, px, qty, note))


class FakeBroker:
    def __init__(self, max_qty=100, error=None, status=None, cancel_ok=True):
        self.max_qty, self.error, self.status, self.cancel_ok = max_qty, error, status, cancel_ok
        self.orders, self.cancels = [], []

    def orderable(self, code, price, ord_dvsn='01'):
        return self.max_qty, Decimal(0)

    def manual_buy(self, code, qty, sess, price=None):
        if self.error:
            raise self.error
        self.orders.append((code, qty, sess.ord_dvsn, sess.exchange, price))
        return OrderResult(code, 'BUY', qty, price or Decimal(0), '777', branch='06010',
                           ord_dvsn=sess.ord_dvsn, exchange=sess.exchange)

    def order_status(self, order_no, symbol, ymd):
        return self.status

    def cancel(self, order):
        self.cancels.append(order)
        return self.cancel_ok


class FakeSell:
    strategy = None

    def __init__(self):
        self.resold = []

    def allow_resell(self, code):
        self.resold.append(code)


class FakeNotifier:
    def __init__(self):
        self.trades, self.sends = [], []

    def trade(self, *a, **k):
        self.trades.append(a)

    def send(self, *a, **k):
        self.sends.append(a)


def req(id_=1, **over):
    row = dict(id=id_, stock_code='005930', stock_name='삼성전자', order_type='MARKET', limit_price=None,
               qty=10, state='REQUESTED', cancel_requested='N', order_no=None, filled_qty=Decimal(0),
               nxt_flag='Y', order_ymd=None)
    row.update(over)
    return row


def make(rows, **broker_kw):
    repo, broker, sell, notifier = FakeRepo(rows), FakeBroker(**broker_kw), FakeSell(), FakeNotifier()
    cfg = SimpleNamespace(user_id=1, krx_aftermarket_enabled=True)
    return ManualBuyExecutor(cfg, broker, repo, sell, notifier), repo, broker, sell, notifier


def test_executor():
    print('\n[5] 실행기 흐름')
    trading = lambda: True   # noqa: E731
    MB.reconcile_wallet = lambda *a, **k: Decimal(5000)   # 계좌 조회 대체

    ex, repo, br, sell, _ = make([req()])
    ex.poll(at(10, 0), trading)
    check('요청 → 주문 → OPEN', repo.rows[1]['state'] == 'OPEN' and len(br.orders) == 1)
    check('주문 내용 그대로', br.orders[0][:4] == ('005930', Decimal(10), '01', 'SOR'))
    check('주문일 기록', repo.rows[1]['order_ymd'] == '20261103')
    check('당일 매도 표시 해제', sell.resold == ['005930'])
    ex.poll(at(10, 0), trading)
    check('다음 폴링에 재주문 안 함', len(br.orders) == 1)

    ex, repo, br, _, _ = make([req(order_type='LIMIT', limit_price=Decimal('70000'))])
    ex.poll(at(10, 0), trading)
    check('지정가 주문', br.orders[0][2] == '00' and br.orders[0][4] == Decimal('70000'))

    ex, repo, br, _, _ = make([req()])
    ex.poll(at(8, 10), trading)
    check('시장가 장외 → 거부, 주문 없음', repo.rows[1]['state'] == 'REJECTED' and br.orders == [])

    ex, repo, br, _, _ = make([req(qty=11)], max_qty=10)
    ex.poll(at(10, 0), trading)
    check('주문가능수량 초과 거부', repo.rows[1]['state'] == 'REJECTED' and '최대 10주' in repo.rows[1]['reason'])
    check('초과 시 주문 없음', br.orders == [])

    ex, repo, br, _, _ = make([req()], max_qty=None)
    ex.poll(at(10, 0), trading)
    check('수량 조회 실패여도 주문 진행', len(br.orders) == 1)

    check('qty_from_pct 버림', qty_from_pct(7, 50) == 3 and qty_from_pct(10, 100) == 10 and qty_from_pct(3, 10) == 0)

    ex, repo, br, _, _ = make([req(qty=0, qty_pct=Decimal('25'))], max_qty=100)
    ex.poll(at(10, 0), trading)
    check('% 시장가 → 수량 확정 후 주문', repo.rows[1]['qty'] == 25 and br.orders[0][1] == Decimal(25) and repo.rows[1]['state'] == 'OPEN')

    ex, repo, br, _, _ = make([req(qty=0, qty_pct=Decimal('100'), order_type='LIMIT', limit_price=Decimal('70000'))], max_qty=7)
    ex.poll(at(10, 0), trading)
    check('% 지정가 100% → 최대수량', br.orders[0][1] == Decimal(7) and br.orders[0][2] == '00')

    ex, repo, br, _, _ = make([req(qty=0, qty_pct=Decimal('10'))], max_qty=5)
    ex.poll(at(10, 0), trading)
    check('% 결과 1주 미만 거부', repo.rows[1]['state'] == 'REJECTED' and br.orders == [] and '10%' in repo.rows[1]['reason'])

    ex, repo, br, _, _ = make([req(qty=0, qty_pct=Decimal('50'))], max_qty=None)
    ex.poll(at(10, 0), trading)
    check('% 인데 수량 조회 실패 → 주문 안 함', repo.rows[1]['state'] == 'REJECTED' and br.orders == [])

    ex, repo, br, _, _ = make([req()])
    ex.poll(at(10, 0), lambda: False)
    check('휴장일 거부', repo.rows[1]['state'] == 'REJECTED' and br.orders == [])

    api_err = KisAPIError.__new__(KisAPIError)
    Exception.__init__(api_err, '주문가능금액 부족')
    ex, repo, _, _, _ = make([req()], error=api_err)
    ex.poll(at(10, 0), trading)
    check('KIS 거부 → REJECTED', repo.rows[1]['state'] == 'REJECTED')

    ex, repo, _, _, nt = make([req()], error=TimeoutError('timeout'))
    ex.poll(at(10, 0), trading)
    check('네트워크 오류 → UNKNOWN', repo.rows[1]['state'] == 'UNKNOWN' and len(nt.sends) == 1)
    ex.poll(at(10, 0), trading)
    check('UNKNOWN 은 재주문 안 함', repo.rows[1]['state'] == 'UNKNOWN')

    ex, repo, _, _, _ = make([req(state='ORDERING')])
    ex.recover_after_boot()
    check('재기동: ORDERING → UNKNOWN', repo.rows[1]['state'] == 'UNKNOWN')

    open_row = dict(state='OPEN', order_no='777', order_ymd='20261103', branch='06010',
                    ord_dvsn='01', exchange='SOR')
    ex, repo, _, _, nt = make([req(**open_row)], status=S(10, 0))
    ex.poll(at(10, 0), trading)
    check('체결 → FILLED', repo.rows[1]['state'] == 'FILLED' and repo.rows[1]['filled_qty'] == 10)
    check('매매로그·알림 1회', len(repo.trade_logs) == 1 and len(nt.trades) == 1)
    ex._next_sync = 0.0
    ex.poll(at(10, 0), trading)
    check('후처리 중복 없음', len(repo.trade_logs) == 1)

    ex, repo, _, _, _ = make([req(**open_row)], status=S(4, 6))
    ex.poll(at(10, 0), trading)
    check('부분체결 진행 표시', repo.rows[1]['state'] == 'OPEN' and repo.rows[1]['filled_qty'] == 4)

    ex, repo, br, _, _ = make([req(cancel_requested='Y', **open_row)], status=S(0, 0))
    ex.poll(at(10, 0), trading)
    check('취소 요청 → 취소 실행', len(br.cancels) == 1 and br.cancels[0].branch == '06010')
    check('취소 확인 → CANCELLED, 로그 없음', repo.rows[1]['state'] == 'CANCELLED' and repo.trade_logs == [])

    ex, repo, br, _, _ = make([req(cancel_requested='Y', **open_row)], status=S(0, 10), cancel_ok=False)
    ex.poll(at(10, 0), trading)
    check('취소 실패 안내·재시도 안 함', repo.rows[1]['cancel_requested'] == 'N' and '취소하지 못' in repo.rows[1]['reason'])

    ex, repo, _, _, _ = make([req(**open_row)], status={'found': False})
    ex.poll(KST.localize(datetime(2026, 11, 4, 8, 0)), trading)
    check('다음 날 조회 불가 → 만료', repo.rows[1]['state'] == 'EXPIRED')

    class Broken(FakeRepo):
        def expire_stale_manual_buys(self, uid, ttl):
            raise RuntimeError("Table doesn't exist")
    ex, *_ = make([])
    ex.repo = Broken()
    ex.poll(at(10, 0), trading)
    check('테이블 미적용이어도 worker 안 죽음', True)


def main():
    test_session()
    test_next_state()
    test_parse()
    test_gate()
    test_executor()
    print(f'\n결과: PASS {len(PASS)} / FAIL {len(FAIL)}')
    if FAIL:
        print('실패:', FAIL)
        sys.exit(1)


if __name__ == '__main__':
    main()
