"""
M3 종목별 단독 매매 — 교대 없이 각자 사고팔면 얼마까지 나오나.

sim_m3_simple_trade.py 는 두 종목을 **교대**로 운용한다(둘 중 하나만 보유).
이 파일은 237350 / 114800 을 **완전히 독립적으로** 돌린다.
    · 각 종목이 자기 신호로만 진입/청산한다
    · 포지션이 없으면 현금. 상대 종목은 쳐다보지 않는다
    · 두 종목을 동시에 들고 있을 수도 있다(자본은 각각 1.0 으로 따로 계산)

네 가지 기준선을 나란히 낸다
    ① Buy&Hold        — 첫 봉 시가 매수 → 마지막 봉 종가.  전략의 하한 비교선
    ② 전략(현 파라미터) — 지금 쓰는 규칙 그대로
    ③ 전략 최적       — 파라미터를 훑어 그 종목에서 나온 최고 조합
    ④ 이론적 상한     — **완전예지(perfect foresight)** 로 매매했을 때의 최대치
                        수수료를 물면서 모든 상승 구간을 다 먹는 경우.
                        규칙으로는 절대 도달 못 하는 천장이다.

    → 달성률 = ② / ④.  이 값이 낮으면 규칙이 놓치는 구간이 많다는 뜻이고,
      ③ / ④ 가 낮으면 **이 지표 조합 자체의 한계**다(파라미터 문제가 아님).

매매 규칙 (sim_m3_simple_trade 와 동일)
    진입: MACD↑ · OBV↑ · MA20↑ · RSI<70  이 confirm 봉 연속 → 다음 봉 시가
    청산: ① 손절/익절/트레일링 (장중 터치)
          ② MACD↓ · OBV↓ · RSI↓ (REVERSE) → 다음 봉 시가
    청산 후 현금 대기, 새로 confirm 을 채우면 재진입.

실행
    poetry run python -m app.test.sim_m3_single
    poetry run python -m app.test.sim_m3_single --sweep          # 파라미터 탐색
    poetry run python -m app.test.sim_m3_single --code 114800 --trades
    poetry run python -m app.test.sim_m3_single --start 2026-07-01
"""
import argparse
import itertools

from app.config.database import dbConn
from app.test import sim_m3_alternate as sim
from app.test.sim_m3_simple_trade import _f
from stock_shared.strategy.backtester import KisBacktester


# ══════════════════════════════════════════════════════════════
# 단일 종목 시뮬레이터
# ══════════════════════════════════════════════════════════════
class SingleSim:
    """한 종목만 사고파는 시뮬레이터.

    M3AlternateSimulator 를 쓰지 않는 이유: 그건 두 종목 상태를 함께 들고
    도는 구조라 '한 종목만' 을 표현하려면 더미 종목을 끼워 넣어야 한다.
    상태 전이가 단순해서 직접 도는 쪽이 읽기 쉽다.
    """

    def __init__(self, *, confirm: int = 3, rsi_max: float = 70.0,
                 fee: float = 0.0015, slippage: float = 0.0,
                 stop_loss: float = 0.02, take_profit: float = None,
                 trail: float = None, trail_activate: float = 0.0,
                 exit_on_reverse: bool = True):
        self.confirm = max(1, int(confirm))
        self.rsi_max = rsi_max
        self.fee = fee
        self.slippage = slippage
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.trail = trail
        self.trail_activate = trail_activate or 0.0
        self.exit_on_reverse = exit_on_reverse

    # ── 신호 ──────────────────────────────────────────────────
    def _buy_signal(self, p: dict, c: dict) -> bool:
        return (_f(c.get('macd')) > _f(p.get('macd'))
                and _f(c.get('obv')) > _f(p.get('obv'))
                and _f(c.get('ema20')) > _f(p.get('ema20'))
                and _f(c.get('rsi')) < self.rsi_max)

    @staticmethod
    def _exit_signal(p: dict, c: dict) -> bool:
        return (_f(c.get('macd')) < _f(p.get('macd'))
                and _f(c.get('obv')) < _f(p.get('obv'))
                and _f(c.get('rsi')) < _f(p.get('rsi')))

    def _line_exit(self, row: dict, entry: float, peak: float):
        o = _f(row.get('open')) or _f(row.get('close'))
        hi = _f(row.get('high')) or o
        lo = _f(row.get('low')) or o
        if self.stop_loss:
            line = entry * (1 - self.stop_loss)
            if lo <= line:
                return 'STOP', min(line, o)
        if self.trail and peak > 0 and (peak - entry) / entry >= self.trail_activate:
            line = peak * (1 - self.trail)
            if lo <= line:
                return 'TRAIL', min(line, o)
        if self.take_profit:
            line = entry * (1 + self.take_profit)
            if hi >= line:
                return 'TP', max(line, o)
        return None, None

    def _fill(self, row: dict, side: str) -> float:
        px = _f(row.get('open')) or _f(row.get('close'))
        if self.slippage:
            px *= (1 + self.slippage) if side == 'buy' else (1 - self.slippage)
        return px

    # ── 본체 ──────────────────────────────────────────────────
    def run(self, code: str, rows: list) -> dict:
        rows = list(rows)
        KisBacktester(strategy=_Dummy()).enrich_rows(rows)
        n = len(rows)
        if n < 3:
            return _empty(code, rows)

        trades, streak = [], 0
        holding = False
        entry_px = entry_dt = entry_bar = peak = None
        pending = None            # 'BUY' | 'CASH'
        pending_reason = 'REVERSE'

        for i in range(1, n):
            row, prev = rows[i], rows[i - 1]

            # 전봉 확정분 체결
            if pending == 'BUY':
                holding = True
                entry_px = self._fill(row, 'buy')
                entry_dt = str(row['datetime'])
                entry_bar = i
                peak = _f(row.get('high')) or entry_px
                pending = None
            elif pending == 'CASH':
                exit_px = self._fill(row, 'sell')
                trades.append(self._close(code, entry_dt, entry_px,
                                          str(row['datetime']), exit_px,
                                          i - entry_bar, pending_reason))
                holding = False
                streak = 0
                pending = None

            # 가격 라인 (장중)
            if holding:
                peak = max(peak, _f(row.get('high')))
                reason, px = self._line_exit(row, entry_px, peak)
                if reason:
                    trades.append(self._close(code, entry_dt, entry_px,
                                              str(row['datetime']), px,
                                              i - entry_bar, reason))
                    holding = False
                    streak = 0
                    continue

            # 신호 판정
            streak = streak + 1 if self._buy_signal(prev, row) else 0
            if i + 1 >= n:
                continue

            if holding:
                if self.exit_on_reverse and self._exit_signal(prev, row):
                    pending, pending_reason = 'CASH', 'REVERSE'
                    streak = 0
            elif streak >= self.confirm:
                pending = 'BUY'
                streak = 0

        if holding:
            last = rows[-1]
            trades.append(self._close(code, entry_dt, entry_px,
                                      str(last['datetime']), _f(last['close']),
                                      n - 1 - entry_bar, 'EOD'))
        return _summarize(code, rows, trades, self.fee)

    def _close(self, code, e_dt, e_px, x_dt, x_px, bars, reason) -> dict:
        gross = (x_px - e_px) / e_px if e_px else 0.0
        return {'coin': code, 'entry_dt': e_dt, 'entry_price': e_px,
                'exit_dt': x_dt, 'exit_price': x_px, 'bars_held': bars,
                'exit_reason': reason, 'ret_gross': gross,
                'ret_net': gross - 2 * self.fee}


class _Dummy:
    """enrich_rows 가 getattr 로 찾는 윈도우 값만 제공하는 껍데기."""
    vol_ma_window = 20
    regime_window = 90
    hma_period = 20


# ══════════════════════════════════════════════════════════════
# 이론적 상한 — 완전예지 DP
# ══════════════════════════════════════════════════════════════
def oracle_max(rows: list, fee: float) -> dict:
    """수수료를 물면서 **모든 상승 구간을 다 먹었을 때**의 최대 수익률.

    미래를 다 아는 상태에서 매매 횟수 제한 없이 최적으로 사고팔았을 때의 값.
    고전적인 '거래비용 있는 최대이익' DP 다.

        cash[i] = max( cash[i-1],  hold[i-1] * P_i * (1-fee) )   ← 팔기
        hold[i] = max( hold[i-1],  cash[i-1] / P_i * (1-fee) )   ← 사기

    종가 기준으로 계산한다. 전략은 다음 봉 시가에 체결하지만, 상한선은
    '이론적으로 가능한 최대' 를 재는 게 목적이라 체결 지연을 넣지 않는다.
    → 실제 규칙이 이 값에 근접하는 건 불가능하다. 천장으로만 쓴다.
    """
    px = [_f(r.get('close')) for r in rows if _f(r.get('close')) > 0]
    if len(px) < 2:
        return {'ret': 0.0, 'trades': 0}

    cash, hold = 1.0, float('-inf')      # hold = 보유 주식수
    n_buy = 0
    for p in px:
        new_cash = max(cash, hold * p * (1 - fee)) if hold > float('-inf') else cash
        new_hold = max(hold, cash / p * (1 - fee))
        if new_hold > hold and new_hold == cash / p * (1 - fee):
            n_buy += 1
        cash, hold = new_cash, new_hold

    return {'ret': cash - 1.0, 'trades': n_buy}


# ══════════════════════════════════════════════════════════════
def _empty(code, rows):
    return {'coin': code, 'trades': 0, 'total_return': 0.0, 'mdd': 0.0,
            'win_rate': 0.0, 'profit_factor': 0.0, 'avg_bars_held': 0.0,
            'exposure': 0.0, 'bars': len(rows), 'by_reason': {},
            'trade_list': [], 'buy_hold': 0.0}


def _summarize(code, rows, trades, fee):
    n = len(trades)
    bh = 0.0
    if len(rows) >= 2:
        first = _f(rows[0].get('open')) or _f(rows[0].get('close'))
        last = _f(rows[-1].get('close'))
        bh = (last - first) / first if first else 0.0

    if n == 0:
        r = _empty(code, rows)
        r['buy_hold'] = round(bh, 4)
        return r

    eq = [1.0]
    for t in trades:
        eq.append(eq[-1] * (1 + t['ret_net']))
    peak, mdd = eq[0], 0.0
    for e in eq:
        peak = max(peak, e)
        if peak > 0:
            mdd = max(mdd, (peak - e) / peak)

    wins = [t['ret_net'] for t in trades if t['ret_net'] > 0]
    losses = [t['ret_net'] for t in trades if t['ret_net'] <= 0]
    gain, loss = sum(wins), abs(sum(losses))
    pf = (gain / loss) if loss > 0 else ('inf' if gain > 0 else 0.0)

    by = {}
    for t in trades:
        agg = by.setdefault(t['exit_reason'], {'n': 0, 'sum': 0.0})
        agg['n'] += 1
        agg['sum'] += t['ret_net']
    for agg in by.values():
        agg['sum'] = round(agg['sum'], 4)

    held = sum(t['bars_held'] for t in trades)
    return {
        'coin': code, 'trades': n,
        'total_return': round(eq[-1] - 1.0, 4),
        'mdd': round(mdd, 4),
        'win_rate': round(len(wins) / n, 4),
        'profit_factor': pf if isinstance(pf, str) else round(pf, 3),
        'avg_bars_held': round(held / n, 1),
        'exposure': round(min(held / max(len(rows) - 1, 1), 1.0), 4),
        'bars': len(rows), 'by_reason': by, 'trade_list': trades,
        'buy_hold': round(bh, 4),
    }


# ══════════════════════════════════════════════════════════════
def sweep_best(rows: list, code: str, fee: float, slippage: float,
               quick: bool = False) -> tuple:
    """파라미터를 훑어 이 종목 최고 조합을 찾는다."""
    if quick:
        grid = itertools.product([2, 3], [65, 70], [0.02], [True])
    else:
        grid = itertools.product(
            [1, 2, 3, 4],                       # confirm
            [60, 65, 70, 100],                  # rsi_max
            [None, 0.01, 0.015, 0.02, 0.03],    # stop_loss
            [True, False],                      # exit_on_reverse
        )
    best, results = None, []
    for cb, rsi, sl, rev in grid:
        r = SingleSim(confirm=cb, rsi_max=rsi, fee=fee, slippage=slippage,
                      stop_loss=sl, exit_on_reverse=rev).run(code, rows)
        r['_params'] = (cb, rsi, sl, rev)
        results.append(r)
        if best is None or r['total_return'] > best['total_return']:
            best = r
    return best, results


def print_one(res: dict, oracle: dict, label: str = ''):
    tr = res['total_return']
    bh = res['buy_hold']
    om = oracle['ret']
    print(f"  {label:<16} 거래{res['trades']:>4}회  수익 {tr:>+8.2%}  "
          f"MDD {res['mdd']:>6.2%}  승률 {res['win_rate']:>5.1%}  "
          f"노출 {res['exposure']:>5.1%}  "
          f"달성률 {(tr / om * 100) if om > 0 else 0:>5.1f}%")


def report(code: str, rows: list, args):
    print()
    print('=' * 96)
    print(f"[{code}]  {len(rows)}봉  "
          f"{rows[0]['datetime']} ~ {rows[-1]['datetime']}")
    print('=' * 96)

    base = SingleSim(confirm=args.confirm, rsi_max=args.rsi, fee=args.fee,
                     slippage=args.slippage, stop_loss=args.stop_loss,
                     take_profit=args.take_profit, trail=args.trail,
                     trail_activate=args.trail_activate,
                     exit_on_reverse=args.exit_on_reverse).run(code, rows)
    oracle = oracle_max(rows, args.fee)

    print(f"  {'구분':<16} {'':>8}      {'수익률':>10}")
    print('  ' + '-' * 88)
    print(f"  {'① Buy&Hold':<16} {'':<10}  수익 {base['buy_hold']:>+8.2%}")
    print_one(base, oracle,
              f"② 전략(CB{args.confirm}/RSI{args.rsi:.0f})")

    best = None
    if args.sweep:
        best, all_res = sweep_best(rows, code, args.fee, args.slippage, args.quick)
        cb, rsi, sl, rev = best['_params']
        print_one(best, oracle, '③ 전략 최적')
        print(f"  {'':<16} └ CB{cb} · RSI<{rsi} · "
              f"손절 {'없음' if sl is None else f'-{sl:.1%}'} · "
              f"이탈청산 {'ON' if rev else 'OFF'}")

        # 상위 5개 — 1등이 얼마나 앞서는지(과최적화 냄새 판별)
        top = sorted(all_res, key=lambda r: r['total_return'], reverse=True)[:5]
        print(f"\n  상위 5개 조합")
        print(f"    {'CB':>3} {'RSI':>4} {'손절':>7} {'이탈':>5} "
              f"{'거래':>5} {'수익률':>9} {'MDD':>7}")
        for r in top:
            c2, r2, s2, v2 = r['_params']
            print(f"    {c2:>3} {r2:>4} "
                  f"{('없음' if s2 is None else f'-{s2:.1%}'):>7} "
                  f"{('ON' if v2 else 'OFF'):>5} {r['trades']:>5} "
                  f"{r['total_return']:>+8.2%} {r['mdd']:>6.2%}")
        spread = top[0]['total_return'] - top[-1]['total_return']
        if spread < 0.02:
            print(f"    ※ 1~5위 격차 {spread:.2%} — 파라미터 민감도가 낮다."
                  f" 아무거나 써도 비슷하다는 뜻.")
        else:
            print(f"    ※ 1~5위 격차 {spread:.2%} — 1등이 우연히 튄 값일 수 있다."
                  f" 구간을 나눠 재현되는지 볼 것.")

    print(f"  {'④ 이론적 상한':<16} 거래{oracle['trades']:>4}회  "
          f"수익 {om_fmt(oracle['ret'])}   ← 완전예지, 도달 불가능한 천장")
    print('  ' + '-' * 88)

    om = oracle['ret']
    if om > 0:
        print(f"  전략이 상한의 {base['total_return'] / om * 100:.1f}% 를 잡았다"
              + (f" (최적 조합은 {best['total_return'] / om * 100:.1f}%)"
                 if best else ""))

    by = base.get('by_reason') or {}
    if by:
        lbl = {'REVERSE': '이탈', 'STOP': '손절', 'TP': '익절',
               'TRAIL': '트레일링', 'EOD': '기간종료'}
        print('\n  청산사유별 (② 기준)')
        for k in ('REVERSE', 'STOP', 'TRAIL', 'TP', 'EOD'):
            if k in by:
                a = by[k]
                print(f"    {lbl.get(k, k):<8} {a['n']:>3}회  "
                      f"수익합 {a['sum']:>+7.2%}  평균 {a['sum'] / a['n']:>+6.2%}")

    if args.trades and base.get('trade_list'):
        print('\n  거래 내역 (② 기준)')
        print(f"    {'#':>3} {'진입':<20} {'청산':<20} {'봉':>4} {'수익':>8}  사유")
        for i, t in enumerate(base['trade_list'], 1):
            print(f"    {i:>3} {t['entry_dt']:<20} {t['exit_dt']:<20} "
                  f"{t['bars_held']:>4} {t['ret_net']:>+7.2%}  {t['exit_reason']}")
    return base, oracle, best


def print_settings(summary: list):
    """스윕 최적값을 user_option_m3 설정으로 옮기는 방법을 출력한다.

    ⚠ 종목마다 최적이 다르게 나올 수 있는데 user_option_m3 는 **유저당 1행**이다.
      두 종목에 같은 파라미터가 적용된다는 뜻. 최적이 갈리면 둘 중 하나를 고르거나
      (보통 정방향 기준), 종목별 파라미터로 스키마를 확장해야 한다.
    """
    rows = [(c, b) for c, _, _, b in summary if b]
    if not rows:
        return
    print()
    print('=' * 96)
    print('설정 반영 (user_option_m3)')
    print('=' * 96)
    for code, b in rows:
        cb, rsi, sl, rev = b['_params']
        print(f"  {code} 최적 : CB{cb} · RSI<{rsi} · "
              f"손절 {'없음' if sl is None else f'-{sl:.1%}'} · "
              f"이탈 {'ON' if rev else 'OFF'}  → {b['total_return']:+.2%}")

    params = {c: b['_params'] for c, b in rows}
    if len(params) == 2 and len(set(params.values())) > 1:
        print()
        print('  ⚠ 두 종목의 최적 조합이 다르다.')
        print('    user_option_m3 는 유저당 1행이라 두 종목에 같은 값이 적용된다.')
        print('    → 한쪽 기준으로 정하거나, 종목별 파라미터로 스키마를 확장해야 한다.')

    cb, rsi, sl, rev = rows[0][1]['_params']
    print()
    print(f'  {rows[0][0]} 기준 UPDATE 문:')
    print(f"""
    INSERT INTO user_option_m3 (user_id, confirm_bars, rsi_overbought,
                                stop_loss_pct, exit_on_reverse)
    VALUES (1, {cb}, {rsi}, {'NULL' if sl is None else f'{sl:.4f}'}, {int(rev)})
    ON DUPLICATE KEY UPDATE
        confirm_bars    = VALUES(confirm_bars),
        rsi_overbought  = VALUES(rsi_overbought),
        stop_loss_pct   = VALUES(stop_loss_pct),
        exit_on_reverse = VALUES(exit_on_reverse);""")
    print('\n  ※ NULL 로 두면 KospiStrategy3 클래스 기본값'
          '(CB3 · RSI<70 · 손절 -2% · 이탈 ON)이 쓰인다.')


def om_fmt(v):
    return f"{v:>+8.2%}" if abs(v) < 100 else f"{v:>+.1f}배"


# ══════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(
        description='M3 종목별 단독 매매 — 교대 없이 각자 사고팔 때의 수익 한계')
    ap.add_argument('--code', help='한 종목만 (기본: 둘 다)')
    ap.add_argument('--confirm', type=int, default=3)
    ap.add_argument('--rsi', type=float, default=70)
    ap.add_argument('--fee', type=float, default=0.0015, help='편도 수수료율')
    ap.add_argument('--slippage', type=float, default=0.0)
    ap.add_argument('--stop-loss', type=float, default=0.02)
    ap.add_argument('--take-profit', type=float, default=0.0)
    ap.add_argument('--trail', type=float, default=0.0)
    ap.add_argument('--trail-activate', type=float, default=0.0)
    ap.add_argument('--no-exit-reverse', dest='exit_on_reverse',
                    action='store_false')
    ap.add_argument('--sweep', action='store_true', help='파라미터 탐색(③)')
    ap.add_argument('--quick', action='store_true', help='탐색 그리드 축소')
    ap.add_argument('--trades', action='store_true', help='거래 내역 출력')
    ap.add_argument('--start')
    ap.add_argument('--end')
    args = ap.parse_args()

    args.stop_loss = args.stop_loss or None
    args.take_profit = args.take_profit or None
    args.trail = args.trail or None

    codes = [args.code] if args.code else [sim.CODE_A, sim.CODE_B]
    session = dbConn.get_session()
    try:
        summary = []
        for code in codes:
            rows = sim.load_rows(session, code, args.start, args.end)
            if len(rows) < 3:
                print(f"[{code}] 봉 부족 ({len(rows)})")
                continue
            base, oracle, best = report(code, rows, args)
            summary.append((code, base, oracle, best))

        if args.sweep:
            print_settings(summary)

        if len(summary) == 2:
            print()
            print('=' * 96)
            print('두 종목 합산 (자본을 반씩 나눠 각각 운용했다고 가정)')
            print('=' * 96)
            a, b = summary[0][1], summary[1][1]
            oa, ob = summary[0][2], summary[1][2]
            print(f"  전략 합산      : "
                  f"{(a['total_return'] + b['total_return']) / 2:+.2%}")
            print(f"  Buy&Hold 합산  : "
                  f"{(a['buy_hold'] + b['buy_hold']) / 2:+.2%}")
            print(f"  이론 상한 합산 : {(oa['ret'] + ob['ret']) / 2:+.2%}")
            print()
            print('  ※ 교대매매(sim_m3_simple_trade)와 직접 비교하려면 이 합산값을 본다.')
            print('    교대는 자본 100%를 한쪽에 몰지만 여기선 50:50 으로 나눈 셈이다.')
    finally:
        session.remove()


if __name__ == '__main__':
    main()
