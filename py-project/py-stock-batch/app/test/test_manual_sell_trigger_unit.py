"""
매도 수기등록(지정가) 방향(trigger_type) 단위 검증 — DB / KIS 불필요.

무엇을 검증하나
    1. tier_hit — UP(이상)/DOWN(이하)/경계값(같으면 도달)/trigger_type 없는 구행(=UP)
    2. 2026-10-08 사고 재현 — 5120 을 UP 으로 등록하면 4860 에서 안 팔리고(이 동작은 그대로),
       DOWN 으로 등록하면 5120·4860 모두에서 팔린다
    3. pick_manual_tier — 도달 티어가 여럿일 때 DOWN 우선·가장 높은 가격부터, UP 은 가장 낮은 가격부터
    4. on_price 통합 — 실제 BaseSellExecutor.on_price 가 DOWN 티어로 _do_sell 을 호출하는가,
       UP 티어 아래 가격에서는 모드 rule(hit_line)로 넘어가지 않고 대기하는가
    5. repository.insert_manual_sell — trigger_type 검증, 컬럼 미적용 DB 에서 UP 허용·DOWN 거절

실행
    poetry run python -m app.test.test_manual_sell_trigger_unit
"""
import sys
from decimal import Decimal

from app.trade_worker import sell_executor as SE
from app.trade_worker.sell_executor import (
    BaseSellExecutor, pick_manual_tier, tier_hit, tier_label, tier_trigger,
)

PASS, FAIL = [], []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print(('  PASS ' if cond else '  FAIL ') + name + (f'  -- {detail}' if detail and not cond else ''))


def T(price, trig=None, id_=1, ratio=1):
    t = {'id': id_, 'sell_price': Decimal(str(price)), 'qty_ratio': Decimal(str(ratio))}
    if trig is not None:
        t['trigger_type'] = trig
    return t


# ── 1. tier_hit ─────────────────────────────────────────────────────────────
def test_tier_hit():
    print('\n[1] tier_hit')
    check('UP: 가격 미달 → 미도달', not tier_hit(T(5120, 'UP'), 5119))
    check('UP: 같으면 도달', tier_hit(T(5120, 'UP'), 5120))
    check('UP: 초과 → 도달', tier_hit(T(5120, 'UP'), 5200))
    check('DOWN: 가격 위 → 미도달', not tier_hit(T(5120, 'DOWN'), 5121))
    check('DOWN: 같으면 도달', tier_hit(T(5120, 'DOWN'), 5120))
    check('DOWN: 아래 → 도달', tier_hit(T(5120, 'DOWN'), 4860))
    check('trigger_type 키 없음(sql/27 미적용 구행) = UP', tier_trigger(T(5120)) == 'UP' and tier_hit(T(5120), 5200))
    check('trigger_type None = UP', tier_trigger({'sell_price': 1, 'trigger_type': None}) == 'UP')
    check('소문자 down 도 DOWN', tier_trigger({'sell_price': 1, 'trigger_type': 'down'}) == 'DOWN')
    check('쓰레기 값은 UP(기존 동작 보존)', tier_trigger({'sell_price': 1, 'trigger_type': 'XYZ'}) == 'UP')
    check('float/문자 가격도 비교됨', tier_hit(T(5120, 'DOWN'), '4860.5'))


# ── 2. 사고 재현 ────────────────────────────────────────────────────────────
def test_incident():
    print('\n[2] 2026-10-08 위메이드맥스 — 평단 5560, 5120/7000, 현재가 4860')
    old_style = [T(5120, 'UP', 17), T(7000, 'UP', 16)]
    check('사고 설정(5120 UP): 4860 에서 안 팔림', pick_manual_tier(old_style, 4860) is None)
    check('사고 설정(5120 UP): 5000 에서도 안 팔림', pick_manual_tier(old_style, 5000) is None)
    fixed = [T(5120, 'DOWN', 17), T(7000, 'UP', 16)]
    check('수정 설정(5120 DOWN): 5121 에서 대기', pick_manual_tier(fixed, 5121) is None)
    check('수정 설정(5120 DOWN): 5120 에서 손절', (pick_manual_tier(fixed, 5120) or {}).get('id') == 17)
    check('수정 설정(5120 DOWN): 갭하락 4860 에서도 손절', (pick_manual_tier(fixed, 4860) or {}).get('id') == 17)
    check('수정 설정: 7000 UP 은 그대로 익절', (pick_manual_tier(fixed, 7000) or {}).get('id') == 16)
    check('수정 설정: 중간 가격 6000 에서는 대기', pick_manual_tier(fixed, 6000) is None)


# ── 3. pick_manual_tier ─────────────────────────────────────────────────────
def test_pick():
    print('\n[3] pick_manual_tier 우선순위')
    ups = [T(100, 'UP', 1), T(110, 'UP', 2), T(120, 'UP', 3)]
    check('UP 여러 개 도달 → 가장 낮은 가격부터', pick_manual_tier(ups, 125)['id'] == 1)
    check('UP 일부만 도달', pick_manual_tier(ups, 105)['id'] == 1 and pick_manual_tier(ups, 99) is None)
    downs = [T(90, 'DOWN', 4), T(95, 'DOWN', 5), T(80, 'DOWN', 6)]
    check('DOWN 여러 개 도달 → 가장 높은 가격부터(먼저 닿는 순서)', pick_manual_tier(downs, 70)['id'] == 5)
    check('DOWN 일부만 도달', pick_manual_tier(downs, 94)['id'] == 5 and pick_manual_tier(downs, 96) is None)
    mixed = [T(100, 'UP', 1), T(120, 'DOWN', 7)]   # 설정 오류로 둘 다 도달(110): 손절 우선
    check('UP·DOWN 동시 도달 → DOWN 우선', pick_manual_tier(mixed, 110)['id'] == 7)
    check('빈 리스트', pick_manual_tier([], 100) is None)


# ── 4. on_price 통합 ────────────────────────────────────────────────────────
class _Log:
    def info(self, *a, **k): pass
    warn = error = debug = info


class _Sess:
    tradable = True
    name = '정규장'


class Exec(BaseSellExecutor):
    """추상 메서드만 채운 최소 구현 — on_price 의 수기등록 분기만 본다."""
    def __init__(self):
        self.sold_calls = []
        self.hit_line_calls = 0
        self.positions = {'101730': {'stock_code': '101730', 'nxt_flag': 'N'}}
        self._sold, self._inflight, self._disabled, self._cooldown = set(), set(), set(), {}
        self._manual_sells = {}
        self._untradable_log = {}
        self.wlog = _Log()

    def _advance_peak(self, *a, **k): pass
    def _session(self, pos): return _Sess()
    def hit_line(self, pos, price):
        self.hit_line_calls += 1
        return 'SELL_STOP'
    def _do_sell(self, symbol, pos, price, reason, sess, manual=None):
        self.sold_calls.append((symbol, price, reason, (manual or {}).get('id')))


def _make_exec():
    # 추상 메서드가 남아 있으면 인스턴스화가 막히므로 비워서 생성
    Exec.__abstractmethods__ = frozenset()
    return Exec()


def test_on_price():
    print('\n[4] on_price 통합 (실제 BaseSellExecutor.on_price)')
    ex = _make_exec()
    ex._manual_sells = {'101730': [T(5120, 'DOWN', 17), T(7000, 'UP', 16)]}

    ex.on_price('101730', Decimal('5300'))
    check('손절선 위(5300) → 아무것도 안 함, 모드 rule 로 안 넘어감',
          not ex.sold_calls and ex.hit_line_calls == 0)

    ex.on_price('101730', Decimal('4860'))
    check('손절선 아래(4860) → DOWN 티어(id=17)로 MANUAL_SELL',
          ex.sold_calls == [('101730', Decimal('4860'), 'MANUAL_SELL', 17)], str(ex.sold_calls))
    check('수기등록이 있으면 hit_line(자동 손절)은 호출되지 않음(기존 정책 유지)', ex.hit_line_calls == 0)

    ex2 = _make_exec()
    ex2._manual_sells = {'101730': [T(5120, 'UP', 17)]}   # 사고 설정
    ex2.on_price('101730', Decimal('4860'))
    check('사고 설정(5120 UP): 4860 에서 여전히 대기 — UP 의미는 바뀌지 않았다',
          not ex2.sold_calls and ex2.hit_line_calls == 0)

    ex3 = _make_exec()
    ex3.on_price('101730', Decimal('4860'))
    check('수기등록 없음 → 기존대로 hit_line 판정(자동 규칙 불변)',
          ex3.hit_line_calls == 1 and ex3.sold_calls and ex3.sold_calls[0][2] == 'SELL_STOP')


# ── 5. repository.insert_manual_sell ────────────────────────────────────────
class _FakeSession:
    def __init__(self, store): self.store = store
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def commit(self): pass
    def execute(self, sql, params=None):
        text = str(sql)
        self.store['sql'] = text
        self.store['params'] = params
        class R:  # noqa: N801
            lastrowid = 99
            def scalar(_self): return 1 if self.store.get('has_col') else 0
        return R()


def test_repository():
    print('\n[5] repository.insert_manual_sell')
    from app.trade_worker import repository as RP
    store = {}
    real = RP.get_session
    RP.get_session = lambda: _FakeSession(store)
    try:
        repo = RP.Repository.__new__(RP.Repository)

        store['has_col'] = True
        repo.insert_manual_sell(3, '101730', 'x', Decimal('5120'), trigger_type='DOWN')
        check('컬럼 있음: INSERT 에 trigger_type 포함 + 값 DOWN',
              'trigger_type' in store['sql'] and store['params'].get('trigger') == 'DOWN', store['sql'])

        repo._trigger_col_ok = False
        repo.insert_manual_sell(3, '101730', 'x', Decimal('7000'))
        check('기본값은 UP', store['params'].get('trigger') == 'UP')

        try:
            repo.insert_manual_sell(3, '101730', 'x', Decimal('7000'), trigger_type='SIDEWAYS')
            check('잘못된 trigger_type 은 ValueError', False)
        except ValueError:
            check('잘못된 trigger_type 은 ValueError', True)

        store.clear(); store['has_col'] = False
        repo2 = RP.Repository.__new__(RP.Repository)
        repo2.insert_manual_sell(3, '101730', 'x', Decimal('7000'), trigger_type='UP')
        check('컬럼 미적용 DB: UP 등록은 기존 INSERT(컬럼 없이)로 성공',
              'trigger_type' not in store['sql'] and 'trigger' not in store['params'], store['sql'])
        try:
            repo2.insert_manual_sell(3, '101730', 'x', Decimal('5120'), trigger_type='DOWN')
            check('컬럼 미적용 DB: DOWN 등록은 거절(UP 으로 조용히 저장 금지)', False)
        except ValueError as e:
            check('컬럼 미적용 DB: DOWN 등록은 거절(UP 으로 조용히 저장 금지)', 'sql/27' in str(e))
    finally:
        RP.get_session = real


def test_label():
    print('\n[6] tier_label')
    check('UP 라벨', tier_label(T('7000.00', 'UP')) == '7000↑익절', tier_label(T('7000.00', 'UP')))
    check('DOWN 라벨', tier_label(T('5120.00', 'DOWN')) == '5120↓손절', tier_label(T('5120.00', 'DOWN')))
    check('소수 가격 보존', tier_label(T('5120.5', 'DOWN')) == '5120.5↓손절')


def main():
    test_tier_hit()
    test_incident()
    test_pick()
    test_on_price()
    test_repository()
    test_label()
    print('\n' + '=' * 70)
    print(f'PASS {len(PASS)} · FAIL {len(FAIL)}')
    print('=' * 70)
    if FAIL:
        print('실패:', FAIL)
        sys.exit(1)


if __name__ == '__main__':
    main()
