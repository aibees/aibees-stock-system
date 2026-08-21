"""
특정 진입/청산 시점이 왜 그렇게 판정됐는지 역추적한다.

"이 시점은 진입점이면 안 되는데 왜 들어갔나" 를 코드가 아니라 **데이터로** 답한다.
시뮬레이션을 그대로 다시 돌린 뒤, 지목한 시각 주변의 봉을 조건별로 펼쳐
어느 봉에서 몇 번째 연속이 채워졌고 어디서 체결됐는지 보여준다.

보여주는 것
    [1] 해당 거래 요약 (진입/청산/보유봉수/수익/사유)
    [2] 진입 확정까지의 봉별 조건 판정 — 두 종목 나란히
        · 4개 조건 각각 Y/· 와 실제 수치(현재값 vs 직전값)
        · 연속 카운트(streak) 와 확정 시점
        · 체결 봉 표시
    [3] 왜 상대 종목이 아니었나 — 동시 확정이면 score 비교
    [4] 보유 구간에서 손절선이 언제 닿았어야 했나
        (손절 미설정으로 큰 손실이 난 거래를 진단)

실행
    poetry run python -m app.test.explain_m3_entry --dt "2026-06-25 15:00:00"
    poetry run python -m app.test.explain_m3_entry --trade 1
    poetry run python -m app.test.explain_m3_entry --trade 1 --lookback 20
    poetry run python -m app.test.explain_m3_entry --list        # 거래 목록만
"""
import argparse

from app.config.database import dbConn
from app.test import sim_m3_alternate as sim
from app.test.sim_m3_simple_trade import SimpleSignalStrategy, _f, run

CONDS = [
    ('macd_up', 'MACD', 'macd'),
    ('obv_up',  'OBV',  'obv'),
    ('ma20_up', 'MA20', 'ema20'),
]


def trace(rows: list, rsi_max: float) -> list:
    """봉별 조건 판정 + 연속 카운트. 시뮬레이터와 동일한 계산."""
    out, streak = [], 0
    for i in range(1, len(rows)):
        p, c = rows[i - 1], rows[i]
        flags = {k: _f(c.get(col)) > _f(p.get(col)) for k, _, col in CONDS}
        flags['rsi_ok'] = _f(c.get('rsi')) < rsi_max
        buy = all(flags.values())
        streak = streak + 1 if buy else 0
        out.append({
            'i': i, 'datetime': str(c['datetime']),
            'open': _f(c.get('open')), 'high': _f(c.get('high')),
            'low': _f(c.get('low')), 'close': _f(c.get('close')),
            'rsi': _f(c.get('rsi')),
            'vals': {col: (_f(c.get(col)), _f(p.get(col))) for _, _, col in CONDS},
            'flags': flags, 'buy': buy, 'streak': streak,
        })
    return out


def _row(t: dict, confirm: int, tag: str = '') -> str:
    f = t['flags']
    m = lambda b: 'Y' if b else '·'                     # noqa: E731
    star = '★' if t['streak'] >= confirm else ' '
    return (f"  {t['datetime'][5:16]:<12} {t['close']:>9,.0f} "
            f"{t['rsi']:>5.1f} "
            f"{m(f['macd_up']):>5} {m(f['obv_up']):>4} {m(f['ma20_up']):>5} "
            f"{m(f['rsi_ok']):>5} {t['streak']:>4}{star} {tag}")


HEAD = (f"  {'시각':<12} {'종가':>9} {'RSI':>5} "
        f"{'MACD':>5} {'OBV':>4} {'MA20':>5} {'RSI<':>5} {'연속':>4}")


def explain(tr_a: list, tr_b: list, trade: dict, confirm: int,
            rsi_max: float, lookback: int, stop_loss: float):
    side_code = trade['coin']
    entry_dt = trade['entry_dt']

    idx_a = {t['datetime']: k for k, t in enumerate(tr_a)}
    idx_b = {t['datetime']: k for k, t in enumerate(tr_b)}
    if entry_dt not in idx_a:
        print(f"  ⚠ {entry_dt} 봉을 찾을 수 없다")
        return
    k = idx_a[entry_dt]

    print()
    print('=' * 92)
    print(f"[1] 거래 요약")
    print('=' * 92)
    print(f"  종목      : {side_code}")
    print(f"  진입      : {trade['entry_dt']}  @ {trade['entry_price']:,.0f}")
    print(f"  청산      : {trade['exit_dt']}  @ {trade['exit_price']:,.0f}")
    print(f"  보유      : {trade['bars_held']}봉  ·  수익 {trade['ret_net']:+.2%}"
          f"  ·  사유 {trade['exit_reason']}")

    # ── [2] 진입 판정 추적 ────────────────────────────────────────
    lo = max(0, k - lookback)
    print()
    print('=' * 92)
    print(f"[2] 진입 판정 추적  (체결 봉 = {entry_dt})")
    print('=' * 92)
    print(f"\n  ── {sim.CODE_A} ──")
    print(HEAD)
    for t in tr_a[lo:k + 1]:
        tag = '← 체결(시가 진입)' if t['datetime'] == entry_dt else ''
        print(_row(t, confirm, tag))

    print(f"\n  ── {sim.CODE_B} ──")
    print(HEAD)
    for t in tr_b[lo:k + 1]:
        tag = '← 같은 시각' if t['datetime'] == entry_dt else ''
        print(_row(t, confirm, tag))

    # ── 확정 봉 특정 ──────────────────────────────────────────────
    # 체결은 '확정 봉의 다음 봉 시가'. 즉 확정은 k-1 봉에서 일어났다.
    if k >= 1:
        conf_a, conf_b = tr_a[k - 1], tr_b[k - 1]
        print()
        print('-' * 92)
        print(f"  확정 봉 : {conf_a['datetime']}  (체결 봉의 직전)")
        print(f"    {sim.CODE_A} streak={conf_a['streak']} "
              f"→ {'확정 ✅' if conf_a['streak'] >= confirm else '미확정'}"
              f" (기준 {confirm}봉)")
        print(f"    {sim.CODE_B} streak={conf_b['streak']} "
              f"→ {'확정 ✅' if conf_b['streak'] >= confirm else '미확정'}")

        # 연속이 어디서 시작됐는지
        if conf_a['streak'] >= confirm:
            s0 = k - conf_a['streak']
            print(f"\n  {sim.CODE_A} 연속 시작 = {tr_a[s0]['datetime']} "
                  f"→ {conf_a['streak']}봉 연속 충족")
            print(f"  조건별 실제값 (확정 봉 {conf_a['datetime']}):")
            for key, name, col in CONDS:
                cur, prv = conf_a['vals'][col]
                d = cur - prv
                print(f"    {name:<5} {cur:>14,.2f}  (직전 {prv:>14,.2f}, "
                      f"Δ{d:>+12,.2f})  {'상승 Y' if d > 0 else '하락 ·'}")
            print(f"    RSI   {conf_a['rsi']:>14,.2f}  "
                  f"(기준 <{rsi_max:.0f})  "
                  f"{'통과 Y' if conf_a['rsi'] < rsi_max else '차단 ·'}")

        # ── [3] 상대 종목과의 비교 ────────────────────────────────
        if conf_a['streak'] >= confirm and conf_b['streak'] >= confirm:
            print()
            print('=' * 92)
            print('[3] 두 종목 동시 확정 → score 로 선택됨')
            print('=' * 92)
            print('  score 계산 내역은 --verbose 로 시뮬을 다시 돌리면 출력된다.')
        elif conf_a['streak'] >= confirm:
            print(f"\n  → {sim.CODE_B} 는 미확정이라 비교 없이 "
                  f"{sim.CODE_A} 단독 진입")

    # ── [4] 보유 구간 손절선 점검 ─────────────────────────────────
    exit_dt = trade['exit_dt']
    tr_side = tr_a if side_code == sim.CODE_A else tr_b
    seg = [t for t in tr_side
           if trade['entry_dt'] <= t['datetime'] <= exit_dt]
    if seg:
        entry_px = trade['entry_price']
        worst = min(seg, key=lambda t: t['low'])
        dd = (worst['low'] - entry_px) / entry_px if entry_px else 0.0
        print()
        print('=' * 92)
        print('[4] 보유 구간 최대 낙폭')
        print('=' * 92)
        print(f"  진입가 {entry_px:,.0f} · 최저가 {worst['low']:,.0f} "
              f"({worst['datetime']}) → {dd:+.2%}")

        for sl in (0.01, 0.02, 0.03, 0.05):
            line = entry_px * (1 - sl)
            hit = next((t for t in seg if t['low'] <= line), None)
            if hit:
                print(f"    손절 -{sl:.0%} (라인 {line:,.0f}) → "
                      f"{hit['datetime']} 에 최초 터치 "
                      f"(진입 후 {seg.index(hit)}봉)")
            else:
                print(f"    손절 -{sl:.0%} (라인 {line:,.0f}) → 미터치")

        if trade['ret_net'] < -0.03 and trade['exit_reason'] == 'FLIP':
            print(f"\n  ⚠ 손실 {trade['ret_net']:.2%} 인데 사유가 FLIP 이다. "
                  f"손절이 꺼진 상태로 돌렸다는 뜻이다.\n"
                  f"    --stop-loss 0.02 로 다시 돌리면 위 표의 시점에서 잘린다.")


# ──────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description='M3 진입/청산 판정 역추적')
    ap.add_argument('--dt', help='진입 시각 "YYYY-MM-DD HH:MM:SS"')
    ap.add_argument('--trade', type=int, help='거래 번호 (1부터)')
    ap.add_argument('--list', action='store_true', help='거래 목록만 출력')
    ap.add_argument('--lookback', type=int, default=12, help='앞쪽 표시 봉 수')
    ap.add_argument('--rsi', type=float, default=70)
    ap.add_argument('--confirm', type=int, default=3)
    ap.add_argument('--stop-loss', type=float, default=0.0,
                    help='시뮬에 적용할 손절 (기본 0=미적용, 원 결과 재현용)')
    ap.add_argument('--fee', type=float, default=0.0015)
    ap.add_argument('--start')
    ap.add_argument('--end')
    args = ap.parse_args()

    session = dbConn.get_session()
    try:
        res = run(session, rsi_max=args.rsi, confirm=args.confirm,
                  fee=args.fee, slippage=0.0,
                  stop_loss=args.stop_loss or None,
                  start=args.start, end=args.end)
        tl = res.get('trade_list') or []
        if not tl:
            print('거래 없음.')
            return

        print(f"[시뮬] {args.confirm}봉 · RSI<{args.rsi:.0f} · "
              f"손절 {'-%.1f%%' % (args.stop_loss * 100) if args.stop_loss else '없음'}"
              f" → 거래 {len(tl)}건")
        print()
        print(f"  {'#':>3} {'종목':<8} {'진입':<20} {'청산':<20} "
              f"{'봉':>4} {'수익':>8}  사유")
        for i, t in enumerate(tl, 1):
            mk = ''
            if args.trade == i or (args.dt and t['entry_dt'] == args.dt):
                mk = '  ←'
            print(f"  {i:>3} {t['coin']:<8} {t['entry_dt']:<20} "
                  f"{t['exit_dt']:<20} {t['bars_held']:>4} "
                  f"{t['ret_net']:>+7.2%}  {t['exit_reason']}{mk}")

        if args.list:
            return

        target = None
        if args.trade:
            if 1 <= args.trade <= len(tl):
                target = tl[args.trade - 1]
        elif args.dt:
            target = next((t for t in tl if t['entry_dt'] == args.dt), None)
        else:
            target = tl[0]

        if target is None:
            print(f"\n⚠ 지정한 거래를 찾을 수 없다. --list 로 목록 확인.")
            return

        from stock_shared.strategy.m3_alternate import M3AlternateSimulator
        rows_a = sim.load_rows(session, sim.CODE_A, args.start, args.end)
        rows_b = sim.load_rows(session, sim.CODE_B, args.start, args.end)
        # 시뮬과 동일하게 교집합 정렬해야 인덱스가 맞는다
        a, b = M3AlternateSimulator.align(rows_a, rows_b)

        explain(trace(a, args.rsi), trace(b, args.rsi),
                target, args.confirm, args.rsi, args.lookback, args.stop_loss)
    finally:
        session.remove()


if __name__ == '__main__':
    main()
