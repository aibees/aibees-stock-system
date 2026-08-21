"""
M3 교대매매 시뮬레이션 — 단순 조건 4개 + 2봉 연속 확정.

매수신호 (전부 AND)
    1) MACD  기울기 상승   macd  > 직전봉 macd
    2) OBV   기울기 상승   obv   > 직전봉 obv
    3) MA20  기울기 상승   ema20 > 직전봉 ema20   (실제로는 20봉 단순이평)
    4) RSI < 70

    → 이 4개가 **3봉 연속** 충족돼야 '확정'. 휩쏘 방어.
      3봉 = 1시간 30분. 2봉보다 보수적이라 교대 횟수가 줄고 수수료가 절약되는
      대신 진입이 늦어진다. --sweep 으로 2봉과 비교할 수 있다.

이탈신호 (보유 중, 3개 전부 AND)
    1) MACD 기울기 하락   macd < 직전봉
    2) OBV  기울기 하락   obv  < 직전봉
    3) RSI  기울기 하락   rsi  < 직전봉
    → **즉시** 청산 후 현금 대기 (사유 REVERSE)

    · 연속 확인 없이 1봉으로 판정한다. 진입은 신중(3봉), 이탈은 빠르게 —
      이 비대칭이 의도다. 손실을 오래 끌고 가는 게 최대 리스크라서.
    · RSI 는 진입에선 **수준**(<70, 과매수 차단), 이탈에선 **기울기**를 본다.
      70 아래여도 계속 내려가고 있으면 이탈이다.
    · MA20 은 이탈 판정에서 뺐다. 후행성이 커서 이미 꺾인 뒤에야 기울기가
      음수로 돌아 청산이 늦는다.
    · --no-exit-reverse 로 끄고 비교할 수 있다.

매매 시나리오 (테스트 시나리오 1 + 손절)
    · 시작   : 두 종목 동시 체크. 둘 다 확정이면 score 높은 쪽 매수.
               한쪽만 확정이면 그쪽.
    · 보유 중: ① 청산 라인(손절/익절/트레일링) 먼저 판정  → 현금
               ② 모멘텀 이탈(REVERSE) 판정               → 현금
               ③ 상대 종목 확정 신호 감시               → 갈아타기(FLIP)
                  ③은 --no-flip-on-signal 로 끌 수 있다
    · 청산 후: **어느 사유든 반대편을 바로 사지 않는다.**
               현금으로 빠진 뒤 두 종목 중 먼저 매수신호(3봉 연속)를 띄우는
               쪽으로 재진입한다. 같은 봉에 둘 다 확정되면 score 로 가른다.
               직전 청산 종목도 후보에 포함된다(streak 리셋으로 새로 채워야 함).

               왜: 내 종목이 꺾였다는 게 곧 상대가 오른다는 뜻은 아니다.
               정·역 ETF 라도 둘 다 방향을 못 잡고 진동하는 구간이 있고,
               무조건 넘어가면 양쪽에서 번갈아 맞으며 수수료만 태운다.
               진입 근거를 항상 '그 종목의 매수신호' 하나로 통일한다.
    · 체결   : 신호/REVERSE → 다음 봉 시가.  라인 → 장중 터치 즉시(갭이면 시가).

기본 손절 -2%
    30분봉 스케일에 맞춘 값이다. KospiStrategy1 의 -5% 는 일봉 기준이라
    30분봉에서는 거의 안 걸린다(실측 30분봉 ATR/종가 0.82%).
    --sweep-stop 으로 손절폭 민감도를 볼 수 있다.

sim_m3_simple_signal.py 가 '신호 지점' 만 찍는다면 이 파일은 그 신호로
실제 매매를 돌려 수익을 낸다. 신호 정의는 두 파일이 동일하다.

실행
    poetry run python -m app.test.sim_m3_simple_trade            # 3봉 · RSI<70
    poetry run python -m app.test.sim_m3_simple_trade --confirm 2 --rsi 65
    poetry run python -m app.test.sim_m3_simple_trade --start 2026-07-01
    poetry run python -m app.test.sim_m3_simple_trade --sweep    # confirm/rsi 민감도
"""
import argparse

from app.config.database import dbConn
from app.test import sim_m3_alternate as sim
from stock_shared.strategy.m3_alternate import M3AlternateSimulator, ScoreConfig


def _f(v, default=0.0) -> float:
    if v is None or v == '':
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


class SimpleSignalStrategy:
    """조건 4개만 보는 매수 판정기.

    M3AlternateSimulator 는 strategy.get_action_with_prev(...) 만 호출하므로
    KospiStrategy1 전체를 흉내 낼 필요가 없다. 그 메서드 하나와,
    KisBacktester.enrich_rows 가 참조하는 윈도우 속성 몇 개면 충분하다.

    KospiStrategy1 을 쓰지 않는 이유:
        국면게이트 / ATR하한 / 거래량하한 등이 겹겹이 걸려 있고,
        그 임계값들이 일봉 기준이라 30분봉에서는 게이트가 영구히 닫힌다
        (실측 atr_ratio 0.82% vs atr_ratio_min 5%).
        여기서는 조건이 4개뿐이라 결과를 그대로 추적할 수 있다.
    """

    # enrich_rows 가 참조하는 값들. 조건 4개는 이걸 안 쓰지만
    # vol_avg / downtrend_ratio 주입 로직이 getattr 로 찾는다.
    vol_ma_window = 20
    regime_window = 90
    hma_period = 20

    def __init__(self, rsi_max: float = 70.0):
        self.rsi_max = rsi_max

    def get_action_with_prev(self, position_type, prev_info, coin_info, user_info):
        macd_up = _f(coin_info.macd) > _f(prev_info.macd)
        obv_up = _f(coin_info.obv) > _f(prev_info.obv)
        ma20_up = _f(coin_info.ema20) > _f(prev_info.ema20)
        rsi_ok = _f(coin_info.rsi) < self.rsi_max
        is_buy = macd_up and obv_up and ma20_up and rsi_ok

        # ── 보유 중: 모멘텀 이탈 판정 ─────────────────────────────
        # MACD↓ AND OBV↓ AND RSI↓ → 즉시 청산(연속 확인 없음).
        #
        # RSI 는 **기울기**로 본다. 진입 조건의 RSI 는 수준(<70, 과매수 차단)이지만
        # 이탈에서는 방향이 문제다. 70 아래여도 계속 내려가고 있으면 이탈이다.
        #
        # 3개 AND 라 2개일 때보다 이탈이 덜 걸린다. 30분봉에서 MACD·OBV 가
        # 동시에 한 봉 꺾이는 건 흔해서 2개만으로는 수수료만 태울 수 있다.
        #
        # MA20 은 여전히 뺀다. 후행성이 커서 이미 꺾인 뒤에야 기울기가
        # 음수로 돌아 청산이 늦어진다.
        if position_type == 'active':
            macd_down = _f(coin_info.macd) < _f(prev_info.macd)
            obv_down = _f(coin_info.obv) < _f(prev_info.obv)
            rsi_down = _f(coin_info.rsi) < _f(prev_info.rsi)
            is_exit = macd_down and obv_down and rsi_down
            return {
                'action_type': 'SELL_TREND' if is_exit else 'HOLD',
                'indicator': {
                    'macd_down': 'Y' if macd_down else 'N',
                    'obv_down': 'Y' if obv_down else 'N',
                    'rsi_down': 'Y' if rsi_down else 'N',
                },
                'todayStock': {'close': _f(coin_info.close)},
            }

        # score 계산용 indicator. 두 종목이 같은 봉에서 동시 확정될 때
        # 우열을 가리는 데만 쓰인다(scoring.tech_score 입력).
        close = _f(coin_info.close)
        atr = _f(coin_info.atr)
        rh = _f(coin_info.recent_high)
        indicator = {
            'macd_slope_up': 'Y' if macd_up else 'N',
            'is_bb_mid_breakout': 'Y' if _f(coin_info.bb_mid_breakout) > 0 else 'N',
            'is_vol_limit': 'Y' if _f(coin_info.volume) > _f(
                getattr(user_info, 'vol_limit', 0)) else 'N',
            'atr_ratio': round(atr / close, 6) if close else 0.0,
            'dip_from_high': round((close - rh) / rh, 6) if rh > 0 else 0.0,
        }
        return {
            'action_type': 'BUY' if is_buy else 'HOLD',
            'indicator': indicator,
            'todayStock': {'close': close, 'volume': _f(coin_info.volume)},
        }


# ──────────────────────────────────────────────────────────────
def run(session, *, rsi_max: float, confirm: int, fee: float, slippage: float,
        stop_loss: float = None, take_profit: float = None,
        trail: float = None, trail_activate: float = 0.0,
        exit_on_reverse: bool = True, flip_on_signal: bool = True,
        start: str = None, end: str = None, score_original: bool = False,
        verbose: bool = False) -> dict:
    sc = ScoreConfig(w_tech=0.5, w_fund=0.3, w_liq=0.2) if score_original else None
    m3 = M3AlternateSimulator(
        SimpleSignalStrategy(rsi_max), SimpleSignalStrategy(rsi_max),
        confirm_bars=confirm, fee_rate=fee, slippage=slippage, score_config=sc,
        stop_loss_pct=stop_loss, take_profit_pct=take_profit,
        trail_drawdown_pct=trail, trail_activate_pct=trail_activate,
        exit_on_reverse=exit_on_reverse, flip_on_signal=flip_on_signal,
    )
    rows_a = sim.load_rows(session, sim.CODE_A, start, end)
    rows_b = sim.load_rows(session, sim.CODE_B, start, end)
    return m3.run(sim.CODE_A, sim.CODE_B, rows_a, rows_b,
                  sim.user_info(session), verbose=verbose)


def print_detail(res: dict, rsi_max: float, confirm: int, fee: float, args=None):
    tr = res['total_return']
    bh_best = max(res['bh_a'], res['bh_b'])

    print()
    print('=' * 84)
    print(f"M3 교대매매 — MACD↑ · OBV↑ · MA20↑ · RSI<{rsi_max:.0f} · {confirm}봉 연속")
    lines = []
    if args:
        if args.stop_loss:
            lines.append(f"손절 -{args.stop_loss:.1%}")
        if args.take_profit:
            lines.append(f"익절 +{args.take_profit:.1%}")
        if args.trail:
            lines.append(f"트레일 -{args.trail:.1%}"
                         f"(활성 +{args.trail_activate:.1%})")
        if args.exit_on_reverse:
            lines.append('이탈청산 ON(3조건)')
        if not args.flip_on_signal:
            lines.append('상대신호교대 OFF')
    print(f"{res['code_a']} ↔ {res['code_b']}   {res['bars']}봉   "
          f"수수료 편도 {fee:.2%}"
          + (f"   [{' · '.join(lines)}]" if lines else "   [청산라인 없음]"))
    print('=' * 84)
    if res.get('note'):
        print(f"  note: {res['note']}")

    print(f"  거래 횟수       : {res['trades']}회")
    print(f"  총수익률        : {tr:+.2%}")
    print(f"  MDD             : {res['mdd']:.2%}")
    print(f"  Calmar(수익/MDD): {res['calmar']}")
    print(f"  승률            : {res['win_rate']:.1%}")
    print(f"  Profit Factor   : {res['profit_factor']}")
    print(f"  평균 보유봉수   : {res['avg_bars_held']}봉 "
          f"(≈{res['avg_bars_held'] / 13:.1f}영업일)")
    print(f"  시장 노출도     : {res.get('exposure', 0):.1%} "
          f"(나머지는 현금 대기)")

    # ── 청산사유별 ────────────────────────────────────────────────
    by = res.get('by_reason') or {}
    if by:
        label = {'FLIP': '교대(상대신호)', 'REVERSE': '이탈(MACD↓OBV↓RSI↓)',
                 'STOP': '손절', 'TP': '익절',
                 'TRAIL': '트레일링', 'EOD': '기간종료'}
        print('\n  ─ 청산사유별 ────────────────────────────────────────────')
        for r in ('FLIP', 'REVERSE', 'STOP', 'TRAIL', 'TP', 'EOD'):
            if r not in by:
                continue
            agg = by[r]
            print(f"  {label.get(r, r):<18} {agg['n']:>3}회  "
                  f"수익합 {agg['sum']:>+7.2%}  "
                  f"평균 {agg['sum'] / agg['n']:>+6.2%}")

    print('\n  ─ 벤치마크 ──────────────────────────────────────────────')
    print(f"  {res['code_a']} Buy&Hold : {res['bh_a']:+.2%}")
    print(f"  {res['code_b']} Buy&Hold : {res['bh_b']:+.2%}")
    print(f"  → 전략 − 최선벤치마크 : {tr - bh_best:+.2%}"
          f"   {'✅ 초과' if tr > bh_best else '❌ 미달'}")

    tl = res.get('trade_list') or []
    if tl:
        print('\n  ─ 거래 내역 ─────────────────────────────────────────────')
        print(f"  {'#':>3} {'종목':<8} {'진입':<20} {'청산':<20} "
              f"{'봉':>4} {'수익':>8}  사유")
        for i, t in enumerate(tl, 1):
            print(f"  {i:>3} {t['coin']:<8} {t['entry_dt']:<20} {t['exit_dt']:<20} "
                  f"{t['bars_held']:>4} {t['ret_net']:>+7.2%}  {t['exit_reason']}")

        # 종목별 기여도 — 어느 쪽에서 벌었는지
        print('\n  ─ 종목별 ────────────────────────────────────────────────')
        for code in (res['code_a'], res['code_b']):
            sub = [t for t in tl if t['coin'] == code]
            if not sub:
                continue
            wins = sum(1 for t in sub if t['ret_net'] > 0)
            tot = sum(t['ret_net'] for t in sub)
            print(f"  {code}: {len(sub)}회 · 승 {wins} · 단순합 {tot:+.2%} · "
                  f"평균 {tot / len(sub):+.2%}")

        eq = res.get('equity') or []
        if eq:
            print(f"\n  자본곡선: 1.0 → {eq[-1]:.4f}  "
                  f"(최고 {max(eq):.4f} / 최저 {min(eq):.4f})")
    print()


def _common(args):
    return dict(fee=args.fee, slippage=args.slippage,
                start=args.start, end=args.end,
                score_original=args.score_original)


def sweep(session, args):
    """confirm / rsi 민감도 — 파라미터가 실제로 결과를 바꾸는지 확인."""
    print()
    print('=' * 90)
    print(f'민감도 ① confirm · RSI  (손절 '
          + (f'-{args.stop_loss:.1%}' if args.stop_loss else '없음') + ' 고정)')
    print('=' * 90)
    print(f"  {'confirm':>7} {'RSI':>5} {'거래':>5} {'수익률':>9} {'MDD':>8} "
          f"{'Calmar':>8} {'승률':>7} {'PF':>8} {'노출':>7}")
    print('  ' + '-' * 84)
    for cb in (1, 2, 3, 4):
        for rsi_max in (60, 65, 70, 100):
            r = run(session, rsi_max=rsi_max, confirm=cb,
                    stop_loss=args.stop_loss, take_profit=args.take_profit,
                    trail=args.trail, trail_activate=args.trail_activate,
                    exit_on_reverse=args.exit_on_reverse,
                    flip_on_signal=args.flip_on_signal, **_common(args))
            mark = ' ←' if (cb == args.confirm and rsi_max == args.rsi) else ''
            print(f"  {cb:>7} {rsi_max:>5} {r['trades']:>5} "
                  f"{r['total_return']:>+8.2%} {r['mdd']:>7.2%} "
                  f"{str(r['calmar']):>8} {r['win_rate']:>6.1%} "
                  f"{str(r['profit_factor']):>8} {r.get('exposure', 0):>6.0%}{mark}")
    print('  ' + '-' * 84)
    print(f'  ← = 현재 설정 ({args.confirm}봉 · RSI<{args.rsi:.0f}).'
          f'  RSI 100 = 사실상 필터 해제')
    print()


def sweep_stop(session, args):
    """손절폭 민감도. 손절이 실제로 도움이 되는지 / 어디가 최적인지."""
    print()
    print('=' * 90)
    print(f'민감도 ② 손절폭  ({args.confirm}봉 · RSI<{args.rsi:.0f} 고정)')
    print('=' * 90)
    print(f"  {'손절':>7} {'거래':>5} {'손절수':>7} {'수익률':>9} {'MDD':>8} "
          f"{'Calmar':>8} {'승률':>7} {'PF':>8} {'노출':>7}")
    print('  ' + '-' * 84)
    for sl in (None, 0.005, 0.01, 0.015, 0.02, 0.03, 0.05):
        r = run(session, rsi_max=args.rsi, confirm=args.confirm,
                stop_loss=sl, take_profit=args.take_profit,
                trail=args.trail, trail_activate=args.trail_activate,
                **_common(args))
        n_stop = (r.get('by_reason') or {}).get('STOP', {}).get('n', 0)
        lbl = '없음' if sl is None else f'-{sl:.1%}'
        mark = ' ←' if sl == args.stop_loss else ''
        print(f"  {lbl:>7} {r['trades']:>5} {n_stop:>7} "
              f"{r['total_return']:>+8.2%} {r['mdd']:>7.2%} "
              f"{str(r['calmar']):>8} {r['win_rate']:>6.1%} "
              f"{str(r['profit_factor']):>8} {r.get('exposure', 0):>6.0%}{mark}")
    print('  ' + '-' * 84)
    print('  손절수 = STOP 으로 청산된 횟수. 0이면 그 손절폭은 한 번도 안 걸린 것.')
    print()


# ──────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description='M3 교대매매 시뮬 (MACD↑·OBV↑·MA20↑·RSI<70, 3봉 연속)')
    ap.add_argument('--rsi', type=float, default=70, help='RSI 상한 (기본 70)')
    ap.add_argument('--confirm', type=int, default=3, help='연속 확인 봉수 (기본 3)')
    ap.add_argument('--fee', type=float, default=0.0015, help='편도 수수료율')
    ap.add_argument('--slippage', type=float, default=0.0, help='편도 슬리피지율')
    # ── 청산 라인 ──────────────────────────────────────────────
    ap.add_argument('--stop-loss', type=float, default=0.02,
                    help='손절 %% (기본 0.02 = -2%%). 0 이면 미사용')
    ap.add_argument('--take-profit', type=float, default=0.0,
                    help='익절 %% (기본 미사용)')
    ap.add_argument('--trail', type=float, default=0.0,
                    help='트레일링 되돌림 %% (기본 미사용)')
    ap.add_argument('--trail-activate', type=float, default=0.0,
                    help='트레일링 활성 수익 %% (고점수익 이 값 초과 시 ON)')
    ap.add_argument('--no-flip-on-signal', dest='flip_on_signal',
                    action='store_false',
                    help='보유 중 상대 신호로 갈아타는 경로를 끈다. '
                         '청산은 REVERSE/가격라인으로만 발생')
    ap.add_argument('--no-exit-reverse', dest='exit_on_reverse',
                    action='store_false',
                    help='보유 종목 MACD↓·OBV↓ 즉시 교대를 끈다(비교용)')
    ap.add_argument('--start', help='시작일 YYYY-MM-DD')
    ap.add_argument('--end', help='종료일 YYYY-MM-DD')
    ap.add_argument('--score-original', action='store_true',
                    help='동시 확정 시 score 가중치를 매수추천배치 원본으로')
    ap.add_argument('--sweep', action='store_true', help='confirm/RSI 민감도 표')
    ap.add_argument('--sweep-stop', action='store_true', help='손절폭 민감도 표')
    ap.add_argument('--verbose', action='store_true', help='교대/청산 시점 로그')
    args = ap.parse_args()

    # 0 은 '미사용' 으로 취급 (argparse 에서 None 을 기본값으로 두면
    # --stop-loss 0 으로 끄는 방법이 없어진다)
    args.stop_loss = args.stop_loss or None
    args.take_profit = args.take_profit or None
    args.trail = args.trail or None

    session = dbConn.get_session()
    try:
        for code in (sim.CODE_A, sim.CODE_B):
            cnt = sim._dao.count_by_coin(session, code)
            b = sim._dao.select_bounds(session, code)
            print(f"[데이터] {code}: {cnt}봉 ({b['first']} ~ {b['last']})")

        res = run(session, rsi_max=args.rsi, confirm=args.confirm,
                  stop_loss=args.stop_loss, take_profit=args.take_profit,
                  trail=args.trail, trail_activate=args.trail_activate,
                  exit_on_reverse=args.exit_on_reverse,
                  flip_on_signal=args.flip_on_signal,
                  verbose=args.verbose, **_common(args))
        print_detail(res, args.rsi, args.confirm, args.fee, args)

        if args.sweep:
            sweep(session, args)
        if args.sweep_stop:
            sweep_stop(session, args)
    finally:
        session.remove()


if __name__ == '__main__':
    main()
