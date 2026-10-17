"""
실시간 매수 라운드(user_options.s1_realtime_buy) 단위 검증 — DB / KIS 불필요.

무엇을 검증하나
    1. 당일 손실 매도 종목은 후보에서 빠지고, 수익 매도 종목은 남는다
    2. 최우선타겟은 손실 매도 종목이어도 남는다(사용자 지정 예외)
    3. 갭 게이트 기준가 = 매수타겟 close (장중 목록이면 배치 시점 가격)
    4. 실시간 라운드는 최우선타겟을 **산 경우에만** 소비하고, 09:00 라운드는 기존대로 항상 소비한다
    5. 손실매도 조회가 실패하면 라운드를 접는다(재매수 방지 우선)

실행
    poetry run python -m app.test.test_realtime_buy_unit
"""
import sys
from decimal import Decimal
from types import SimpleNamespace

from app.trade_worker.modes.mode_1.buy_executor1 import BuyExecutor1

PASS, FAIL = [], []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('  PASS ' if cond else '  FAIL ') + name + (f'  -- {detail}' if detail and not cond else ''))


class FakeRepo:
    def __init__(self, targets, loss_codes=(), priority=None, loss_fail=False):
        self.targets = targets
        self.loss_codes = set(loss_codes)
        self.priority = priority
        self.loss_fail = loss_fail
        self.cleared = 0

    def insert_worker_log(self, *a, **k): pass
    def get_holding_positions(self, uid, exclude_exclusive=False): return []
    def get_wallet_balance(self, uid): return Decimal('1000000')
    def get_latest_buy_target_ymd(self, min_ymd=None): return '20261017'
    def get_buy_targets(self, ymd, order_spec=None): return [dict(t) for t in self.targets]
    def get_priority_target(self, uid): return self.priority

    def clear_priority_target(self, uid):
        self.cleared += 1
        self.priority = None
        return True

    def get_today_loss_exit_codes(self, uid):
        if self.loss_fail:
            raise RuntimeError('db down')
        return self.loss_codes


class FakeBroker:
    def __init__(self, prices):
        self.prices = prices
    def prev_trading_day(self): return '20261016'
    def current_price(self, code, nxt=False): return Decimal(str(self.prices[code]))
    def orderable(self, code, price, ord_dvsn='01'): return (10, Decimal('1000000'))


def make(targets, prices, **repo_kw):
    cfg = SimpleNamespace(user_id=9, buy_budget_ratio=0.98, nxt_limit_slip_pct=2.0)
    meta = SimpleNamespace(s1_gap_block_pct=Decimal('0.02'), s1_buy_order=None, s1_realtime_buy=1)
    strategy = SimpleNamespace(user_meta=meta, halted=False)
    repo = FakeRepo(targets, **repo_kw)
    ex = BuyExecutor1(cfg, FakeBroker(prices), repo, notifier=None, strategy=strategy)
    bought = []

    def fake_place(cand, price, qty, balance, premarket, tag):
        bought.append((cand.code, price, tag))
        return True
    ex._place_and_settle = fake_place
    return ex, repo, bought


T = lambda code, close: {'stock_code': code, 'stock_name': code, 'close': close, 'nxt_flag': 'N'}


def test_loss_exclusion():
    print('\n[1] 당일 손실 매도 종목 제외')
    ex, repo, bought = make([T('AAA', 1000), T('BBB', 2000)], {'AAA': 1000, 'BBB': 2000},
                            loss_codes={'AAA'})
    ex.run(realtime=True)
    check('손실 매도 AAA 건너뛰고 BBB 매수', bought and bought[0][0] == 'BBB', bought)
    check('라운드 태그 = 실시간', bought and bought[0][2] == '실시간', bought)

    ex, repo, bought = make([T('AAA', 1000), T('BBB', 2000)], {'AAA': 1000, 'BBB': 2000},
                            loss_codes=set())
    ex.run(realtime=True)
    check('손실 매도 없으면(수익 매도 포함) 1위 AAA 매수', bought and bought[0][0] == 'AAA', bought)

    ex, repo, bought = make([T('AAA', 1000), T('BBB', 2000)], {'AAA': 1000, 'BBB': 2000},
                            loss_codes={'AAA'})
    ex.run()
    check('09:00 라운드에는 손실 제외를 적용하지 않음', bought and bought[0][0] == 'AAA', bought)


def test_priority_exception_and_consume():
    print('\n[2] 최우선타겟 예외 · 소비 규칙')
    ex, repo, bought = make([T('AAA', 1000), T('BBB', 2000)], {'AAA': 1000, 'BBB': 2000},
                            loss_codes={'BBB'}, priority='BBB')
    ex.run(realtime=True)
    check('손실 매도 종목이어도 최우선타겟이면 매수', bought and bought[0][0] == 'BBB', bought)
    check('실시간 라운드에서 최우선타겟을 샀으면 소비', repo.cleared == 1)

    ex, repo, bought = make([T('AAA', 1000)], {'AAA': 1000}, priority='ZZZ')
    ex.run(realtime=True)
    check('목록에 없는 최우선타겟은 실시간 라운드에서 소비하지 않음', repo.cleared == 0 and repo.priority == 'ZZZ')

    ex, repo, bought = make([T('AAA', 1000), T('BBB', 1000)], {'AAA': 1000, 'BBB': 1000}, priority='BBB')
    ex._place_and_settle = lambda *a, **k: False      # 주문 거부 → 아무것도 못 삼
    ex.run(realtime=True)
    check('실시간 라운드에서 못 샀으면 최우선타겟 유지', repo.cleared == 0 and repo.priority == 'BBB')

    ex, repo, bought = make([T('AAA', 1000)], {'AAA': 1000}, priority='ZZZ')
    ex.run()
    check('09:00 라운드는 기존대로 항상 소비', repo.cleared == 1)


def test_gap_ref():
    print('\n[3] 갭 기준가 = 매수타겟 close')
    # 장중 목록: AAA close=1050(배치 시점 가격). 현재가 1060 → 갭 0.95% → 통과
    ex, repo, bought = make([T('AAA', 1050)], {'AAA': 1060})
    ex.run(realtime=True)
    check('배치 시점 가격 대비 +0.95% → 매수', bought and bought[0][0] == 'AAA', bought)
    # 현재가 1100 → 갭 4.8% > 2% → skip, 다음 후보 BBB
    ex, repo, bought = make([T('AAA', 1050), T('BBB', 500)], {'AAA': 1100, 'BBB': 505})
    ex.run(realtime=True)
    check('배치 시점 가격 대비 +4.8% → AAA skip, BBB 매수', bought and bought[0][0] == 'BBB', bought)


def test_loss_query_fail():
    print('\n[4] 손실매도 조회 실패')
    ex, repo, bought = make([T('AAA', 1000)], {'AAA': 1000}, loss_fail=True)
    ex.run(realtime=True)
    check('조회 실패 → 실시간 라운드 매수 없음', not bought, bought)
    check('last_bought_code 없음', ex.last_bought_code is None)


if __name__ == '__main__':
    test_loss_exclusion()
    test_priority_exception_and_consume()
    test_gap_ref()
    test_loss_query_fail()
    print(f'\n결과: PASS {len(PASS)} / FAIL {len(FAIL)}')
    sys.exit(1 if FAIL else 0)
