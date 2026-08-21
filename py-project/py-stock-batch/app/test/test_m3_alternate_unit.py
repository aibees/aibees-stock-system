"""
M3 교대매매 시뮬레이터 단위 검증 (DB / KIS 불필요).

무엇을 검증하나
    1. scoring.tech_score 가 추출 전 StockService._tech_score 와 수치가 동일한가
       (리팩터링으로 스코어가 바뀌면 매수추천 랭킹이 조용히 달라진다)
    2. align() 이 두 종목 봉을 교집합으로 맞추는가
    3. confirm_bars 연속 확인이 실제로 동작하는가 (1회 신호로는 진입 안 함)
    4. 교대 시나리오가 명세대로 도는가
       — 최초 진입은 score 높은 쪽
       — 보유 중엔 상대 신호에만 반응
       — 상대 신호 확정 시 매도+매수가 같은 봉에서 일어남
    5. 수익률/MDD 집계가 맞는가

전략을 mock 으로 갈아끼워 신호 시퀀스를 직접 통제한다.
KospiStrategy1 자체는 기존 백테스트에서 이미 검증된 영역이라 여기선 다루지 않는다.

실행
    poetry run python -m app.test.test_m3_alternate_unit
"""
from stock_shared.dto.userOptionMeta import UserOptionMeta
from stock_shared.strategy import scoring
from stock_shared.strategy.m3_alternate import M3AlternateSimulator, ScoreConfig

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = ''):
    (PASS if cond else FAIL).append(name)
    mark = 'PASS' if cond else 'FAIL'
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ''))


# ══════════════════════════════════════════════════════════════
# 1. score 동치성 — 추출 전 원본 구현을 그대로 재현해 비교
# ══════════════════════════════════════════════════════════════
def _legacy_tech_score(ind: dict) -> float:
    """리팩터링 전 StockService._tech_score 원본 (비교 기준)."""
    def _to_float(v):
        try:
            if v is None:
                return None
            s = str(v).replace('%', '').replace(',', '').strip()
            if s in ('', '-', 'N/A'):
                return None
            return float(s)
        except (ValueError, TypeError):
            return None

    LO, HI = 0.05, 0.12
    DLO, DHI = 0.03, 0.15

    macd_slope_up = ind.get('macd_slope_up')
    if macd_slope_up is None:
        macd_slope_up = 'Y' if ind.get('macd_cross') == 'G' else 'N'
    macd = 1.0 if macd_slope_up == 'Y' else 0.4

    bb = 1.0 if ind.get('is_bb_mid_breakout') == 'Y' else 0.0
    vl = 1.0 if ind.get('is_vol_limit') == 'Y' else 0.0

    ar = _to_float(ind.get('atr_ratio'))
    if ar is None:
        atr = 0.0
    elif ar <= LO:
        atr = 0.0
    elif ar >= HI:
        atr = 1.0
    else:
        atr = (ar - LO) / (HI - LO)

    dip = _to_float(ind.get('dip_from_high'))
    if dip is None:
        dip_score = 0.0
    else:
        d = abs(dip)
        if d <= DLO:
            dip_score = 0.0
        elif d >= DHI:
            dip_score = 1.0
        else:
            dip_score = (d - DLO) / (DHI - DLO)

    return 0.30 * macd + 0.15 * bb + 0.20 * vl + 0.20 * atr + 0.15 * dip_score


def test_score_equivalence():
    print('\n[1] score 동치성 (추출 전 ↔ 후)')
    cases = [
        {},
        {'macd_slope_up': 'Y', 'is_bb_mid_breakout': 'Y', 'is_vol_limit': 'Y',
         'atr_ratio': 0.118, 'dip_from_high': -0.193},
        {'macd_slope_up': 'N', 'atr_ratio': 0.05, 'dip_from_high': -0.03},
        {'macd_cross': 'G', 'atr_ratio': 0.20, 'dip_from_high': -0.50},   # 폴백 경로
        {'macd_slope_up': 'Y', 'atr_ratio': '8.9%', 'dip_from_high': None},
        {'atr_ratio': 'N/A', 'dip_from_high': '-'},
        {'macd_slope_up': 'Y', 'atr_ratio': 0.085, 'dip_from_high': -0.09,
         'is_vol_limit': 'Y'},
    ]
    worst = 0.0
    for i, c in enumerate(cases):
        a, b = _legacy_tech_score(c), scoring.tech_score(c)
        worst = max(worst, abs(a - b))
        check(f'case{i} tech_score', abs(a - b) < 1e-12, f'{a:.6f} vs {b:.6f}')
    check('최대 오차 < 1e-12', worst < 1e-12, f'{worst:.2e}')

    # total_score 원본 가중치 재현
    tech, fund, liq = 0.7, 0.4, 1.0
    legacy = 100.0 * (0.5 * tech + 0.3 * fund + 0.2 * liq)
    now = scoring.total_score(tech, fund, liq)
    check('total_score 원본 가중치', abs(legacy - now) < 1e-12, f'{legacy} vs {now}')

    # liq 정규화: 후보 2개면 항상 1.0 / 0.0 (M3 편향 경고의 근거)
    liqs = scoring.normalize_liquidity([1e10, 1e8])
    check('normalize_liquidity 2종목 → [1.0, 0.0]',
          liqs == [1.0, 0.0], str(liqs))
    check('normalize_liquidity 동일값 → 전원 1.0',
          scoring.normalize_liquidity([5.0, 5.0]) == [1.0, 1.0])


# ══════════════════════════════════════════════════════════════
# mock 전략 — 신호 시퀀스를 직접 지정
# ══════════════════════════════════════════════════════════════
class MockStrategy:
    """datetime → 매수신호 여부 / tech 점수를 표로 받아 그대로 돌려준다."""
    vol_ma_window = 20
    regime_window = 90
    hma_period = 20

    def __init__(self, signals: dict, techs: dict = None):
        self.signals = signals          # {datetime: True/False}
        self.techs = techs or {}        # {datetime: 0.0~1.0}

    def get_action_with_prev(self, _pos, _prev, coin_info, _ui):
        dt = str(coin_info.datetime)
        is_buy = self.signals.get(dt, False)
        tech = self.techs.get(dt, 0.0)
        # tech 를 그대로 만들어내는 indicator 조합: macd(0.30) + vol(0.20) 사용
        ind = {}
        if tech >= 0.5:
            ind = {'macd_slope_up': 'Y', 'is_vol_limit': 'Y'}      # 0.30+0.20 = 0.50
        elif tech > 0:
            ind = {'macd_slope_up': 'Y'}                            # 0.30
        else:
            ind = {'macd_slope_up': 'N'}                            # 0.12
        return {
            'action_type': 'BUY' if is_buy else 'HOLD',
            'indicator': ind,
            'todayStock': {'close': coin_info.close, 'volume': coin_info.volume},
        }


def _bars(prices: list, start_hour: int = 9) -> list:
    """가격 리스트 → 30분봉 rows. open=close=지정가(체결가 계산 단순화)."""
    rows = []
    for i, p in enumerate(prices):
        h, m = divmod(start_hour * 60 + i * 30, 60)
        rows.append({
            'datetime': f'2026-08-03 {h:02d}:{m:02d}:00',
            'open': float(p), 'high': float(p) * 1.001,
            'low': float(p) * 0.999, 'close': float(p),
            'volume': 100000.0, 'ema20': float(p), 'ema60': float(p),
            'macd': 0.0, 'macd_s': 0.0, 'obv': 0.0, 'obv_signal': 0.0,
            'rsi': 50.0, 'atr': float(p) * 0.01, 'bb_upper': float(p) * 1.1,
            'bb_mid': float(p), 'bb_lower': float(p) * 0.9,
            'recent_high': float(p), 'bb_mid_breakout': 0.0, 'vol_surge_n': 0.0,
        })
    return rows


def _ui():
    ui = UserOptionMeta()
    ui.vol_limit = 0
    ui.vol_surge = 3.0
    ui.delay_date = 5
    ui.macd_recent_day = 20
    ui.bb_over_recent_day = 7
    return ui


# ══════════════════════════════════════════════════════════════
# 2. align
# ══════════════════════════════════════════════════════════════
def test_align():
    print('\n[2] align — 교집합 정렬')
    a = _bars([100, 101, 102, 103])
    b = _bars([200, 201, 202, 203])
    del b[1]                                    # B 에서 2번째 봉 누락
    aa, bb = M3AlternateSimulator.align(a, b)
    check('길이 일치', len(aa) == len(bb) == 3, f'{len(aa)} / {len(bb)}')
    check('시각 일치', all(x['datetime'] == y['datetime'] for x, y in zip(aa, bb)))
    check('누락 봉 제외', all(r['datetime'] != a[1]['datetime'] for r in aa))


# ══════════════════════════════════════════════════════════════
# 3. confirm_bars
# ══════════════════════════════════════════════════════════════
def test_confirm_bars():
    print('\n[3] confirm_bars — 연속 확인')
    dts = [r['datetime'] for r in _bars([0] * 8)]

    # A 는 1회만 신호 (idx2), B 는 신호 없음
    sig_once = {dts[2]: True}
    sim = M3AlternateSimulator(MockStrategy(sig_once), MockStrategy({}),
                               confirm_bars=2, fee_rate=0.0)
    res = sim.run('A', 'B', _bars([100] * 8), _bars([200] * 8), _ui())
    check('1회 신호 + confirm=2 → 진입 없음', res['trades'] == 0,
          f"trades={res['trades']}")

    # A 가 2회 연속 (idx2,3)
    sig_twice = {dts[2]: True, dts[3]: True}
    sim = M3AlternateSimulator(MockStrategy(sig_twice), MockStrategy({}),
                               confirm_bars=2, fee_rate=0.0)
    res = sim.run('A', 'B', _bars([100] * 8), _bars([200] * 8), _ui())
    check('2회 연속 + confirm=2 → 진입', res['trades'] == 1,
          f"trades={res['trades']}")
    if res['trade_list']:
        # idx3 에서 확정 → idx4 시가 체결
        check('체결 시점 = 확정 다음 봉',
              res['trade_list'][0]['entry_dt'] == dts[4],
              res['trade_list'][0]['entry_dt'])

    # 끊긴 신호(idx2, idx4)는 연속이 아니다
    sig_gap = {dts[2]: True, dts[4]: True}
    sim = M3AlternateSimulator(MockStrategy(sig_gap), MockStrategy({}),
                               confirm_bars=2, fee_rate=0.0)
    res = sim.run('A', 'B', _bars([100] * 8), _bars([200] * 8), _ui())
    check('끊긴 신호 → 진입 없음 (휩쏘 방어)', res['trades'] == 0,
          f"trades={res['trades']}")

    # confirm=1 이면 1회로 진입
    sim = M3AlternateSimulator(MockStrategy(sig_once), MockStrategy({}),
                               confirm_bars=1, fee_rate=0.0)
    res = sim.run('A', 'B', _bars([100] * 8), _bars([200] * 8), _ui())
    check('confirm=1 → 1회 신호로 진입', res['trades'] == 1,
          f"trades={res['trades']}")


# ══════════════════════════════════════════════════════════════
# 4. score 선점 + 교대
# ══════════════════════════════════════════════════════════════
def test_score_pick_and_flip():
    print('\n[4] 최초 진입 score 선점 + 교대')
    dts = [r['datetime'] for r in _bars([0] * 12)]

    # 둘 다 idx2,3 에 신호. B 의 tech 가 더 높다 → B 선택
    both = {dts[2]: True, dts[3]: True}
    sim = M3AlternateSimulator(
        MockStrategy(both, {dts[2]: 0.3, dts[3]: 0.3}),      # A tech 0.30
        MockStrategy(both, {dts[2]: 0.6, dts[3]: 0.6}),      # B tech 0.50
        confirm_bars=2, fee_rate=0.0)
    res = sim.run('AAA', 'BBB', _bars([100] * 12), _bars([200] * 12), _ui())
    check('동시 확정 → score 높은 B 선택',
          bool(res['trade_list']) and res['trade_list'][0]['coin'] == 'BBB',
          res['trade_list'][0]['coin'] if res['trade_list'] else '없음')

    # 교대 시나리오: A 먼저 진입(idx1,2) → B 신호(idx5,6) → 교대
    sim = M3AlternateSimulator(
        MockStrategy({dts[1]: True, dts[2]: True}),
        MockStrategy({dts[5]: True, dts[6]: True}),
        confirm_bars=2, fee_rate=0.0)
    # A 가격 100→110 (+10%), B 는 평평
    pa = [100, 100, 100, 100, 105, 110, 110, 110, 110, 110, 110, 110]
    res = sim.run('AAA', 'BBB', _bars(pa), _bars([200] * 12), _ui())
    tl = res['trade_list']
    check('교대 발생 → 거래 2건 (A청산 + B 최종청산)', len(tl) == 2,
          f'{len(tl)}건')
    if len(tl) == 2:
        check('1번째=A, 2번째=B', tl[0]['coin'] == 'AAA' and tl[1]['coin'] == 'BBB',
              f"{tl[0]['coin']} / {tl[1]['coin']}")
        check('A 청산시각 == B 진입시각 (동시 교대)',
              tl[0]['exit_dt'] == tl[1]['entry_dt'],
              f"{tl[0]['exit_dt']} vs {tl[1]['entry_dt']}")
        check('2번째 청산사유 = EOD', tl[1]['exit_reason'] == 'EOD',
              tl[1]['exit_reason'])

    # 보유 중 '자기 종목' 신호는 무시돼야 한다
    sim = M3AlternateSimulator(
        MockStrategy({dts[1]: True, dts[2]: True,      # 진입
                      dts[5]: True, dts[6]: True,      # 보유 중 자기 신호 (무시 대상)
                      dts[8]: True, dts[9]: True}),
        MockStrategy({}),                               # B 는 신호 없음
        confirm_bars=2, fee_rate=0.0)
    res = sim.run('AAA', 'BBB', _bars([100] * 12), _bars([200] * 12), _ui())
    check('보유 중 자기 신호 무시 → 거래 1건', res['trades'] == 1,
          f"trades={res['trades']}")


# ══════════════════════════════════════════════════════════════
# 5. 성과 집계
# ══════════════════════════════════════════════════════════════
def test_metrics():
    print('\n[5] 성과 집계')
    dts = [r['datetime'] for r in _bars([0] * 12)]

    # A: idx1,2 확정 → idx3 시가(=100) 진입, B: idx5,6 확정 → idx7 시가 청산
    pa = [100, 100, 100, 100, 100, 100, 100, 110, 110, 110, 110, 110]
    sim = M3AlternateSimulator(
        MockStrategy({dts[1]: True, dts[2]: True}),
        MockStrategy({dts[5]: True, dts[6]: True}),
        confirm_bars=2, fee_rate=0.0)
    res = sim.run('AAA', 'BBB', _bars(pa), _bars([200] * 12), _ui())
    tl = res['trade_list']
    check('A 진입가 100', tl and abs(tl[0]['entry_price'] - 100) < 1e-9,
          str(tl[0]['entry_price']) if tl else '')
    check('A 청산가 110', tl and abs(tl[0]['exit_price'] - 110) < 1e-9,
          str(tl[0]['exit_price']) if tl else '')
    check('A 수익 +10% (수수료 0)', tl and abs(tl[0]['ret_net'] - 0.10) < 1e-9,
          f"{tl[0]['ret_net']:.4f}" if tl else '')

    # 수수료 반영: 편도 0.15% → 왕복 0.3%
    sim = M3AlternateSimulator(
        MockStrategy({dts[1]: True, dts[2]: True}),
        MockStrategy({dts[5]: True, dts[6]: True}),
        confirm_bars=2, fee_rate=0.0015)
    res2 = sim.run('AAA', 'BBB', _bars(pa), _bars([200] * 12), _ui())
    t0 = res2['trade_list'][0]
    check('수수료 왕복 0.3% 차감', abs(t0['ret_net'] - (0.10 - 0.003)) < 1e-9,
          f"{t0['ret_net']:.4f}")

    # MDD: -10% 손실 1건이면 MDD 10%
    pa_loss = [100, 100, 100, 100, 100, 100, 100, 90, 90, 90, 90, 90]
    sim = M3AlternateSimulator(
        MockStrategy({dts[1]: True, dts[2]: True}),
        MockStrategy({dts[5]: True, dts[6]: True}),
        confirm_bars=2, fee_rate=0.0)
    res3 = sim.run('AAA', 'BBB', _bars(pa_loss), _bars([200] * 12), _ui())
    check('MDD 10% (−10% 거래 1건)', abs(res3['mdd'] - 0.10) < 1e-6,
          f"{res3['mdd']:.4f}")

    # Buy&Hold 벤치마크
    check('bh_a = +10%', abs(res['bh_a'] - 0.10) < 1e-6, f"{res['bh_a']:.4f}")
    check('bh_b = 0%', abs(res['bh_b']) < 1e-6, f"{res['bh_b']:.4f}")

    # 거래 0건일 때 안전하게 떨어지는가
    sim = M3AlternateSimulator(MockStrategy({}), MockStrategy({}),
                               confirm_bars=2, fee_rate=0.0)
    res4 = sim.run('AAA', 'BBB', _bars([100] * 12), _bars([200] * 12), _ui())
    check('거래 0건 → 예외 없이 0 리턴',
          res4['trades'] == 0 and res4['total_return'] == 0.0 and res4['mdd'] == 0.0)


# ══════════════════════════════════════════════════════════════
def main():
    print('=' * 70)
    print('M3 교대매매 시뮬레이터 단위 검증')
    print('=' * 70)
    test_score_equivalence()
    test_align()
    test_confirm_bars()
    test_score_pick_and_flip()
    test_metrics()

    print()
    print('=' * 70)
    print(f"PASS {len(PASS)} · FAIL {len(FAIL)}")
    if FAIL:
        for f in FAIL:
            print(f"  ✗ {f}")
    print('=' * 70)
    return 1 if FAIL else 0


if __name__ == '__main__':
    raise SystemExit(main())
