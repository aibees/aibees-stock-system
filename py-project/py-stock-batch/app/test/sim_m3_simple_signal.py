"""
M3 단순 매수신호 테스트 — 조건 4개만으로 각 종목의 매수지점을 찍는다.

조건 (전부 AND)
    1) MACD  기울기 상승   : macd  > 직전봉 macd
    2) OBV   기울기 상승   : obv   > 직전봉 obv
    3) MA20  기울기 상승   : ema20 > 직전봉 ema20
                             ※ 컬럼명은 ema20 이지만 실제 값은 20봉 단순이평이다
                                (bb_mid 와 동일값인 것으로 확인됨)
    4) RSI 과매수 아님      : rsi < 70

KospiStrategy1 을 쓰지 않고 조건을 직접 계산한다.
    이유: 전략 클래스에는 국면게이트·ATR하한·거래량하한 등 게이트가 겹겹이
    걸려 있어 "왜 신호가 안 뜨는지" 를 눈으로 쫓기 어렵다. 여기서는 조건 4개가
    전부라 각 봉에서 무엇이 막았는지 그대로 보인다.

출력
    · 종목별 매수지점 목록 (시각 / 종가 / 조건별 Y·N / 연속 신호 횟수)
    · 조건별 단독 통과율 — 어느 조건이 병목인지 즉시 드러난다
    · 연속 3봉 확정(휩쏘 방어) 적용 시 신호 수 비교

실행
    poetry run python -m app.test.sim_m3_simple_signal              # RSI<70 · 3봉
    poetry run python -m app.test.sim_m3_simple_signal --rsi 65 --confirm 2
    poetry run python -m app.test.sim_m3_simple_signal --start 2026-07-01
    poetry run python -m app.test.sim_m3_simple_signal --all-bars   # 전 봉 상태 출력
"""
import argparse

from app.config.database import dbConn
from app.test import sim_m3_alternate as sim

CONDS = ('macd_up', 'obv_up', 'ma20_up', 'rsi_ok')
COND_LABEL = {
    'macd_up': 'MACD↑',
    'obv_up':  'OBV↑',
    'ma20_up': 'MA20↑',
    'rsi_ok':  'RSI<',
}


def _f(v, default=0.0) -> float:
    """Decimal / None / '' → float."""
    if v is None or v == '':
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def evaluate(rows: list, rsi_max: float) -> list:
    """각 봉의 조건 판정 결과를 리스트로 반환.

    첫 봉은 직전봉이 없어 기울기를 못 구하므로 제외한다.
    """
    out = []
    for i in range(1, len(rows)):
        p, c = rows[i - 1], rows[i]
        rsi = _f(c.get('rsi'))
        flags = {
            'macd_up': _f(c.get('macd'))  > _f(p.get('macd')),
            'obv_up':  _f(c.get('obv'))   > _f(p.get('obv')),
            'ma20_up': _f(c.get('ema20')) > _f(p.get('ema20')),
            'rsi_ok':  rsi < rsi_max,
        }
        out.append({
            'datetime': str(c['datetime']),
            'close': _f(c.get('close')),
            'rsi': rsi,
            'macd_delta': _f(c.get('macd')) - _f(p.get('macd')),
            'obv_delta':  _f(c.get('obv'))  - _f(p.get('obv')),
            'ma20_delta': _f(c.get('ema20')) - _f(p.get('ema20')),
            'flags': flags,
            'buy': all(flags.values()),
        })
    return out


def add_streak(evals: list) -> list:
    """연속 신호 횟수를 각 봉에 붙인다(휩쏘 방어용 confirm 판정 근거)."""
    streak = 0
    for e in evals:
        streak = streak + 1 if e['buy'] else 0
        e['streak'] = streak
    return evals


# ──────────────────────────────────────────────────────────────
def report(code: str, evals: list, rsi_max: float, confirm: int, show_all: bool):
    n = len(evals)
    if n == 0:
        print(f"\n[{code}] 판정 가능한 봉이 없다")
        return

    buys = [e for e in evals if e['buy']]
    confirmed = [e for e in evals if e['streak'] >= confirm]

    print()
    print('=' * 96)
    print(f"[{code}]  전체 {n}봉  ·  {evals[0]['datetime']} ~ {evals[-1]['datetime']}")
    print('=' * 96)

    # ── 조건별 단독 통과율 (병목 진단) ────────────────────────────
    print('  조건별 단독 통과율')
    for k in CONDS:
        hit = sum(1 for e in evals if e['flags'][k])
        bar = '█' * int(hit / n * 40)
        lbl = COND_LABEL[k] + (f'{rsi_max:.0f}' if k == 'rsi_ok' else '')
        print(f"    {lbl:<8} {hit:>5}/{n}  {hit / n:>6.1%}  {bar}")

    print(f"\n  4개 AND 충족    : {len(buys)}회 ({len(buys) / n:.1%})")
    print(f"  {confirm}봉 연속 확정  : {len(confirmed)}회 "
          f"({len(confirmed) / n:.1%})  ← 휩쏘 방어 적용 시")

    # 연속 길이 분포 — confirm 값을 몇으로 둘지 판단 근거
    runs, cur = [], 0
    for e in evals:
        if e['buy']:
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    if runs:
        from collections import Counter
        dist = Counter(runs)
        summary = ' '.join(f'{k}봉×{v}' for k, v in sorted(dist.items()))
        print(f"  연속 구간 분포  : {summary}  (총 {len(runs)}구간, "
              f"최장 {max(runs)}봉)")

    # 병목 진단: 신호가 0이면 어느 조건 때문인지 짚어준다
    if not buys:
        worst = min(CONDS, key=lambda k: sum(1 for e in evals if e['flags'][k]))
        hit = sum(1 for e in evals if e['flags'][worst])
        print(f"\n  ⚠ 신호 0건. 최저 통과율 조건 = {COND_LABEL[worst]} "
              f"({hit}/{n}, {hit / n:.1%})")

    # ── 매수지점 목록 ─────────────────────────────────────────────
    target = evals if show_all else buys
    if not target:
        return

    print()
    print('  ' + '-' * 92)
    head = (f"  {'시각':<20} {'종가':>9} {'RSI':>6} "
            f"{'MACD↑':>6} {'OBV↑':>6} {'MA20↑':>6} {'RSI<':>6} {'연속':>4}")
    print(head)
    print('  ' + '-' * 92)

    for e in target:
        f = e['flags']
        mark = lambda b: ' Y' if b else ' ·'          # noqa: E731
        star = '★' if e['streak'] >= confirm else ' '
        print(f"  {e['datetime']:<20} {e['close']:>9,.0f} {e['rsi']:>6.1f} "
              f"{mark(f['macd_up']):>6} {mark(f['obv_up']):>6} "
              f"{mark(f['ma20_up']):>6} {mark(f['rsi_ok']):>6} "
              f"{e['streak']:>4}{star}")

    print('  ' + '-' * 92)
    print(f'  ★ = {confirm}봉 연속 확정 (실제 주문 시점)')


def compare(code_a: str, ev_a: list, code_b: str, ev_b: list):
    """두 종목 신호가 같은 봉에서 겹치는지 — 교대매매 성립 여부 판단용."""
    print()
    print('=' * 96)
    print('두 종목 신호 대조')
    print('=' * 96)

    ma = {e['datetime']: e for e in ev_a}
    mb = {e['datetime']: e for e in ev_b}
    common = sorted(set(ma) & set(mb))
    if not common:
        print('  공통 봉 없음')
        return

    both = [d for d in common if ma[d]['buy'] and mb[d]['buy']]
    only_a = [d for d in common if ma[d]['buy'] and not mb[d]['buy']]
    only_b = [d for d in common if mb[d]['buy'] and not ma[d]['buy']]
    none = len(common) - len(both) - len(only_a) - len(only_b)

    print(f"  공통 봉 {len(common)}개")
    print(f"    {code_a} 만 신호 : {len(only_a):>5}회 ({len(only_a) / len(common):.1%})")
    print(f"    {code_b} 만 신호 : {len(only_b):>5}회 ({len(only_b) / len(common):.1%})")
    print(f"    동시 신호       : {len(both):>5}회 ({len(both) / len(common):.1%})"
          f"  ← score 로 우열을 가려야 하는 구간")
    print(f"    둘 다 없음      : {none:>5}회 ({none / len(common):.1%})")

    if both:
        print(f"\n  동시 신호 시각 (앞 10개)")
        for d in both[:10]:
            print(f"    {d}   {code_a} {ma[d]['close']:>9,.0f}   "
                  f"{code_b} {mb[d]['close']:>9,.0f}")

    # 정방향/인버스라 동시 신호가 많으면 신호 자체가 방향성을 못 잡고 있다는 뜻
    if both and len(both) / len(common) > 0.15:
        print(f"\n  ⚠ 동시 신호 비율이 {len(both) / len(common):.1%} 로 높다. "
              f"정·역 ETF 인데 같은 방향 신호가 자주 뜬다는 건\n"
              f"    이 조건 조합이 방향성을 잘 못 가른다는 뜻이다.")


# ──────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description='M3 단순 매수신호 (MACD↑ · OBV↑ · MA20↑ · RSI<70, 3봉 연속)')
    ap.add_argument('--rsi', type=float, default=70, help='RSI 상한 (기본 70)')
    ap.add_argument('--confirm', type=int, default=3, help='연속 확인 봉수 (기본 3)')
    ap.add_argument('--start', help='시작일 YYYY-MM-DD')
    ap.add_argument('--end', help='종료일 YYYY-MM-DD')
    ap.add_argument('--all-bars', action='store_true',
                    help='매수지점만이 아니라 전 봉 상태 출력')
    args = ap.parse_args()

    session = dbConn.get_session()
    try:
        evs = {}
        for code in (sim.CODE_A, sim.CODE_B):
            rows = sim.load_rows(session, code, args.start, args.end)
            cnt = len(rows)
            print(f"[데이터] {code}: {cnt}봉"
                  + (f" ({rows[0]['datetime']} ~ {rows[-1]['datetime']})" if cnt else ""))
            evs[code] = add_streak(evaluate(rows, args.rsi))

        for code in (sim.CODE_A, sim.CODE_B):
            report(code, evs[code], args.rsi, args.confirm, args.all_bars)

        compare(sim.CODE_A, evs[sim.CODE_A], sim.CODE_B, evs[sim.CODE_B])
    finally:
        session.remove()


if __name__ == '__main__':
    main()
