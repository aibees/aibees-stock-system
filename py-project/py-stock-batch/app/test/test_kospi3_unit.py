"""
KospiStrategy3 단위 검증 (DB / KIS 불필요).

무엇을 검증하나
    1. configure — user_option_m3(s3_*) 값이 실제로 반영되는가, NULL 이면 기본값 유지
    2. 진입 4조건 판정 + confirm_bars 연속 확인
    3. buy_streak 가 상태를 안 들고 매번 같은 답을 내는가(재시작 안전성)
    4. 청산 — 손절/익절/트레일링/모멘텀이탈 우선순위
    5. **sim_m3_single 시뮬레이터와 동일 판정** — 전략을 바꿔 끼워도 결과가 같아야
       백테스트 수치를 실매매 근거로 쓸 수 있다

실행
    poetry run python -m app.test.test_kospi3_unit
"""
from stock_shared.dto.userOptionMeta import UserOptionMeta
from stock_shared.strategy import Action, KospiStrategy3, STRATEGY_BY_MODE
from stock_shared.vo.userCoinInfo import UserCoinInfo

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = ''):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ''))


def bar(dt, o=100, h=100, l=100, c=100, macd=0, obv=0, ema20=100, rsi=50):
    return {'datetime': dt, 'coin': '237350',
            'open': float(o), 'high': float(h), 'low': float(l), 'close': float(c),
            'volume': 1000.0, 'macd': float(macd), 'macd_s': 0.0,
            'obv': float(obv), 'obv_signal': 0.0,
            'ema20': float(ema20), 'ema60': float(ema20), 'rsi': float(rsi),
            'atr': 1.0, 'bb_upper': 9e9, 'bb_mid': float(ema20), 'bb_lower': 0.0,
            'recent_high': float(h), 'bb_mid_breakout': 0.0, 'vol_surge_n': 0.0}


def seq(specs):
    """[(macd, obv, ema20, rsi), ...] → 30분봉 리스트"""
    out = []
    for i, sp in enumerate(specs):
        hh, mm = divmod(9 * 60 + i * 30, 60)
        dt = f'2026-08-12 {hh:02d}:{mm:02d}:00'
        if len(sp) == 4:
            m, o, e, r = sp
            out.append(bar(dt, macd=m, obv=o, ema20=e, rsi=r))
        else:
            op, hi, lo, cl, m, o, e, r = sp
            out.append(bar(dt, op, hi, lo, cl, m, o, e, r))
    return out


def ui(**kw):
    u = UserOptionMeta()
    u.vol_limit = 0
    u.vol_surge = 3.0
    u.delay_date = 5
    u.macd_recent_day = 20
    u.bb_over_recent_day = 7
    u.entry_price = 0.0
    u.avg_price = 0.0
    u.peak_high = 0.0
    u.bars_held = 0
    for k, v in kw.items():
        setattr(u, k, v)
    return u


# ══════════════════════════════════════════════════════════════
def test_registry():
    print('\n[0] 등록 확인')
    check('STRATEGY_BY_MODE["M3"] == KospiStrategy3',
          STRATEGY_BY_MODE.get('M3') is KospiStrategy3)
    check('Action.SELL_TREND 존재', hasattr(Action, 'SELL_TREND'),
          f'value={getattr(Action, "SELL_TREND", None)}')
    s = KospiStrategy3()
    check('기본 confirm_bars=3', s.confirm_bars == 3)
    check('기본 손절 -2% (일봉용 -5% 아님)', s.stop_loss_pct == 0.02,
          str(s.stop_loss_pct))


def test_configure():
    print('\n[1] configure — s3_* 주입')
    s = KospiStrategy3()
    s.configure(ui())                       # 전부 None
    check('전 항목 NULL → 기본값 유지',
          s.confirm_bars == 3 and s.rsi_overbought == 70
          and s.stop_loss_pct == 0.02 and s.exit_on_reverse is True)

    s2 = KospiStrategy3()
    s2.configure(ui(s3_confirm_bars=2, s3_rsi_overbought=65,
                    s3_stop_loss_pct='0.0150', s3_exit_on_reverse=0,
                    s3_enable_ma20_up='N', s3_use_trailing=1,
                    s3_trail_drawdown_pct=0.01, s3_trail_activate_pct=0,
                    s3_long_code='069500'))
    check('confirm_bars 2', s2.confirm_bars == 2, str(s2.confirm_bars))
    check('rsi_overbought 65', s2.rsi_overbought == 65)
    check('stop_loss 문자열 Decimal 파싱', abs(s2.stop_loss_pct - 0.015) < 1e-9,
          str(s2.stop_loss_pct))
    check('exit_on_reverse 0 → False', s2.exit_on_reverse is False)
    check("enable_ma20_up 'N' → False", s2.enable_ma20_up is False)
    check('use_trailing 1 → True', s2.use_trailing is True)
    check('trail_activate 0 은 0 으로 유지(즉시활성)',
          s2.trail_activate_pct == 0.0, str(s2.trail_activate_pct))
    check('long_code 덮어쓰기', s2.long_code == '069500')

    s3 = KospiStrategy3()
    s3.configure(ui(s3_confirm_bars=0))
    check('confirm_bars 0 → 1 로 보정', s3.confirm_bars == 1)


def test_entry():
    print('\n[2] 진입 — 4조건 + confirm_bars')
    s = KospiStrategy3()
    s.configure(ui())                        # confirm 3

    # 봉1,2,3 연속 충족
    rows = seq([(0, 0, 100, 50), (1, 10, 101, 50),
                (2, 20, 102, 50), (3, 30, 103, 50)])
    r = s.get_result_with_action(rows, ui())
    check('3봉 연속 → BUY', r['action_type'] == 'BUY',
          f"streak={r['indicator']['streak']}")

    # 마지막 봉에서 RSI 초과 → 차단
    rows2 = seq([(0, 0, 100, 50), (1, 10, 101, 50),
                 (2, 20, 102, 50), (3, 30, 103, 75)])
    r2 = s.get_result_with_action(rows2, ui())
    check('RSI 75 → HOLD', r2['action_type'] == 'HOLD',
          f"rsi_ok={r2['indicator']['rsi_ok']}")

    # 2봉만 연속 (중간에 끊김)
    rows3 = seq([(0, 0, 100, 50), (1, 10, 101, 50),
                 (0, 5, 100, 50), (1, 10, 101, 50), (2, 20, 102, 50)])
    r3 = s.get_result_with_action(rows3, ui())
    check('연속 2봉뿐 → HOLD', r3['action_type'] == 'HOLD',
          f"streak={r3['indicator']['streak']}")

    # 이력 부족
    r4 = s.get_result_with_action(seq([(0, 0, 100, 50), (1, 10, 101, 50)]), ui())
    check('이력 부족 → HOLD + note', r4['action_type'] == 'HOLD'
          and 'note' in r4['indicator'], r4['indicator'].get('note', ''))

    # confirm=1 이면 1봉으로 진입
    s1 = KospiStrategy3()
    s1.configure(ui(s3_confirm_bars=1))
    r5 = s1.get_result_with_action(seq([(0, 0, 100, 50), (1, 10, 101, 50)]), ui())
    check('confirm=1 → 1봉으로 BUY', r5['action_type'] == 'BUY')

    # 조건 off 스위치
    s6 = KospiStrategy3()
    s6.configure(ui(s3_confirm_bars=1, s3_enable_obv_up=0))
    r6 = s6.get_result_with_action(
        seq([(0, 50, 100, 50), (1, 10, 101, 50)]), ui())   # obv 하락
    check('enable_obv_up=0 → OBV 무시하고 BUY', r6['action_type'] == 'BUY')


def test_streak_stateless():
    print('\n[3] buy_streak — 무상태(재시작 안전)')
    s = KospiStrategy3()
    s.configure(ui())
    rows = seq([(0, 0, 100, 50), (1, 10, 101, 50),
                (2, 20, 102, 50), (3, 30, 103, 50)])
    a = s.buy_streak(rows)
    b = s.buy_streak(rows)
    fresh = KospiStrategy3()
    fresh.configure(ui())
    c = fresh.buy_streak(rows)
    check('같은 입력 → 같은 결과 (반복 호출)', a == b == 3, f'{a}/{b}')
    check('새 인스턴스도 동일 결과', c == a, f'{c} vs {a}')

    rows_break = seq([(0, 0, 100, 50), (1, 10, 101, 50), (0, 5, 100, 50)])
    check('끊긴 직후 streak=0', s.buy_streak(rows_break) == 0,
          str(s.buy_streak(rows_break)))


def test_exit():
    print('\n[4] 청산 — 우선순위')
    s = KospiStrategy3()
    s.configure(ui())                        # 손절 -2%, 이탈 ON

    prev = UserCoinInfo.from_dict(bar('t0', macd=3, obv=30, ema20=103, rsi=60))

    # 손절
    cur = UserCoinInfo.from_dict(bar('t1', c=97, macd=2, obv=25, ema20=103, rsi=55))
    r = s.get_action_in_active(prev, cur, ui(entry_price=100.0, peak_high=100.0))
    check('종가 97 → SELL_STOP_LOSS', r['action_type'] == 'SELL_STOP_LOSS',
          r['sell_ctx']['sell_reason'])
    check('손절선 98.0', r['sell_ctx']['stop_price'] == 98.0,
          str(r['sell_ctx']['stop_price']))

    # 모멘텀 이탈 (가격은 손절선 위)
    cur2 = UserCoinInfo.from_dict(bar('t1', c=99, macd=2, obv=25, ema20=103, rsi=55))
    r2 = s.get_action_in_active(prev, cur2, ui(entry_price=100.0, peak_high=100.0))
    check('MACD↓·OBV↓·RSI↓ → SELL_TREND', r2['action_type'] == 'SELL_TREND',
          r2['indicator'])

    # RSI 상승이면 이탈 아님 (3조건 AND)
    cur3 = UserCoinInfo.from_dict(bar('t1', c=99, macd=2, obv=25, ema20=103, rsi=65))
    r3 = s.get_action_in_active(prev, cur3, ui(entry_price=100.0, peak_high=100.0))
    check('RSI↑ 면 이탈 아님 → HOLD', r3['action_type'] == 'HOLD',
          f"rsi_down={r3['indicator']['rsi_down']}")

    # 손절 우선 (둘 다 걸림)
    cur4 = UserCoinInfo.from_dict(bar('t1', c=97, macd=2, obv=25, ema20=103, rsi=55))
    r4 = s.get_action_in_active(prev, cur4, ui(entry_price=100.0, peak_high=100.0))
    check('손절+이탈 동시 → 손절 우선', r4['action_type'] == 'SELL_STOP_LOSS')

    # 익절
    s5 = KospiStrategy3()
    s5.configure(ui(s3_take_profit_pct=0.05))
    cur5 = UserCoinInfo.from_dict(bar('t1', c=106, macd=4, obv=40, ema20=104, rsi=65))
    r5 = s5.get_action_in_active(prev, cur5, ui(entry_price=100.0, peak_high=106.0))
    check('종가 106 → SELL_PROFIT', r5['action_type'] == 'SELL_PROFIT')

    # 트레일링
    s6 = KospiStrategy3()
    s6.configure(ui(s3_use_trailing=1, s3_trail_drawdown_pct=0.02,
                    s3_trail_activate_pct=0.03, s3_stop_loss_pct=0.20))
    cur6 = UserCoinInfo.from_dict(bar('t1', c=107, macd=4, obv=40, ema20=104, rsi=65))
    r6 = s6.get_action_in_active(prev, cur6, ui(entry_price=100.0, peak_high=110.0))
    check('고점110 대비 -2% 라인(107.8) 하회 → SELL_TRAIL',
          r6['action_type'] == 'SELL_TRAIL', str(r6['sell_ctx']['trail_line']))

    # 트레일링 미활성 (고점수익 < activate)
    s7 = KospiStrategy3()
    s7.configure(ui(s3_use_trailing=1, s3_trail_drawdown_pct=0.02,
                    s3_trail_activate_pct=0.15, s3_stop_loss_pct=0.20))
    r7 = s7.get_action_in_active(prev, cur6, ui(entry_price=100.0, peak_high=110.0))
    check('고점수익 10% < 활성15% → 트레일링 미발동',
          r7['action_type'] != 'SELL_TRAIL',
          f"trail_on={r7['indicator']['trail_on']}")

    # 이탈 OFF
    s8 = KospiStrategy3()
    s8.configure(ui(s3_exit_on_reverse=0))
    r8 = s8.get_action_in_active(prev, cur2, ui(entry_price=100.0, peak_high=100.0))
    check('exit_on_reverse=0 → HOLD', r8['action_type'] == 'HOLD')


def test_matches_simulator():
    print('\n[5] 시뮬레이터(sim_m3_single)와 동일 판정')
    # sim_m3_single.SingleSim 의 조건식을 그대로 재현해 비교한다.
    # 두 곳이 갈리면 백테스트 수치를 실매매 근거로 쓸 수 없다.
    def _f(v, d=0.0):
        try:
            return float(v) if v not in (None, '') else d
        except (TypeError, ValueError):
            return d

    def sim_buy(p, c, rsi_max=70.0):
        return (_f(c['macd']) > _f(p['macd']) and _f(c['obv']) > _f(p['obv'])
                and _f(c['ema20']) > _f(p['ema20']) and _f(c['rsi']) < rsi_max)

    def sim_exit(p, c):
        return (_f(c['macd']) < _f(p['macd']) and _f(c['obv']) < _f(p['obv'])
                and _f(c['rsi']) < _f(p['rsi']))

    s = KospiStrategy3()
    s.configure(ui())

    import random
    random.seed(20260813)
    rows = [bar('t0', macd=0, obv=0, ema20=100, rsi=50)]
    for i in range(1, 400):
        prev = rows[-1]
        rows.append(bar(
            f't{i}',
            macd=prev['macd'] + random.uniform(-2, 2),
            obv=prev['obv'] + random.uniform(-50, 50),
            ema20=prev['ema20'] + random.uniform(-1, 1),
            rsi=min(95, max(5, prev['rsi'] + random.uniform(-8, 8)))))

    mismatch_buy = mismatch_exit = 0
    for i in range(1, len(rows)):
        p, c = rows[i - 1], rows[i]
        pi, ci = UserCoinInfo.from_dict(p), UserCoinInfo.from_dict(c)
        if s.is_buy_bar(pi, ci) != sim_buy(p, c):
            mismatch_buy += 1
        if s.is_reverse_bar(pi, ci) != sim_exit(p, c):
            mismatch_exit += 1

    check(f'진입 1봉 판정 {len(rows) - 1}개 전부 일치', mismatch_buy == 0,
          f'불일치 {mismatch_buy}')
    check(f'이탈 1봉 판정 {len(rows) - 1}개 전부 일치', mismatch_exit == 0,
          f'불일치 {mismatch_exit}')

    # confirm 연속 카운트도 동일한지
    sim_streak, mismatch_streak = 0, 0
    for i in range(1, len(rows)):
        sim_streak = sim_streak + 1 if sim_buy(rows[i - 1], rows[i]) else 0
        strat = s.buy_streak(rows[:i + 1])
        # buy_streak 는 confirm_bars 도달 시 조기 종료하므로 상한을 맞춰 비교
        if min(sim_streak, s.confirm_bars) != min(strat, s.confirm_bars):
            mismatch_streak += 1
    check('연속 카운트 일치(confirm 상한 기준)', mismatch_streak == 0,
          f'불일치 {mismatch_streak}')


def main():
    print('=' * 70)
    print('KospiStrategy3 단위 검증')
    print('=' * 70)
    test_registry()
    test_configure()
    test_entry()
    test_streak_stateless()
    test_exit()
    test_matches_simulator()

    print()
    print('=' * 70)
    print(f'PASS {len(PASS)} · FAIL {len(FAIL)}')
    for f in FAIL:
        print(f'  ✗ {f}')
    print('=' * 70)
    return 1 if FAIL else 0


if __name__ == '__main__':
    raise SystemExit(main())
