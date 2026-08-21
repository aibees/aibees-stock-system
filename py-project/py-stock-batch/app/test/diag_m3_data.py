"""
trade_candle_30m 데이터 건전성 진단.

최적화 결과가 이상할 때(파라미터를 바꿔도 결과가 동일 / 벤치마크 수익률이
비현실적 / 거래가 거의 안 나옴) 전략을 의심하기 전에 데이터를 먼저 본다.

검사 항목
    A. 적재 현황 — 봉 수, 기간, 일자별 봉 수(정상 13봉)
    B. 가격 연속성 — 봉간 급변동, 0/음수 가격
    C. 정·역 상관 — KODEX 코스피100 vs 인버스 봉별 수익률 상관계수.
       진짜 인버스라면 -0.95 이하여야 한다. 아니면 데이터가 섞였거나 깨진 것.
    D. Buy&Hold 검증 — 시뮬레이터가 쓰는 값과 동일 계산 + 현실성 판정
    E. 지표 컬럼 건전성 — macd_g_cross_n / obv_g_cross_n 값 분포.
       String(1) 컬럼에 fillna(0.0) 이 들어가면 'G' 비교가 영원히 False 가 된다.
    F. 신호 재현 — KospiStrategy1 을 실제로 돌려 봉별 매수신호 발생 횟수 집계

실행
    poetry run python -m app.test.diag_m3_data
    poetry run python -m app.test.diag_m3_data --start 2026-06-01
"""
import argparse
from collections import Counter, defaultdict

from app.config.database import dbConn
from app.test import sim_m3_alternate as sim
from stock_shared.strategy.backtester import KisBacktester
from stock_shared.vo.userCoinInfo import UserCoinInfo

ISSUES = []


def warn(msg: str):
    ISSUES.append(msg)
    print(f"    ⚠ {msg}")


# ──────────────────────────────────────────────────────────────
def sec_a(rows_map: dict):
    print('\n[A] 적재 현황')
    for code, rows in rows_map.items():
        if not rows:
            warn(f'{code}: 데이터 없음')
            continue
        by_day = defaultdict(int)
        for r in rows:
            by_day[str(r['datetime'])[:10]] += 1

        print(f"  {code}: {len(rows)}봉 · {len(by_day)}일 · "
              f"{rows[0]['datetime']} ~ {rows[-1]['datetime']}")

        if len(rows) < 250:
            warn(f'{code}: 250봉 미만({len(rows)}) — 지표 워밍업 부족')

        # 정규장 09:00~15:30 → 하루 13봉이 정상
        abnormal = {d: c for d, c in by_day.items() if c != 13}
        if abnormal:
            sample = list(sorted(abnormal.items()))[:8]
            warn(f'{code}: 13봉이 아닌 날 {len(abnormal)}일 → {sample}')

        # 봉 시각 분포 (09:00~15:00 13종이 정상)
        times = Counter(str(r['datetime'])[11:16] for r in rows)
        unexpected = {t: c for t, c in times.items()
                      if t not in {f'{h:02d}:{m:02d}'
                                   for h in range(9, 16) for m in (0, 30)}}
        if unexpected:
            warn(f'{code}: 예상 밖 봉 시각 → {unexpected}')


def sec_b(rows_map: dict):
    print('\n[B] 가격 연속성')
    for code, rows in rows_map.items():
        if len(rows) < 2:
            continue
        bad_px = [r for r in rows
                  if not all(float(r.get(k) or 0) > 0 for k in ('open', 'high', 'low', 'close'))]
        if bad_px:
            warn(f'{code}: 0/음수 가격 {len(bad_px)}봉 → {bad_px[0]["datetime"]} 등')

        # OHLC 정합성: low <= min(open,close) <= max(open,close) <= high
        bad_ohlc = []
        for r in rows:
            o, h, l, c = (float(r.get(k) or 0) for k in ('open', 'high', 'low', 'close'))
            if not (l <= min(o, c) and max(o, c) <= h and l <= h):
                bad_ohlc.append(r['datetime'])
        if bad_ohlc:
            warn(f'{code}: OHLC 정합성 위반 {len(bad_ohlc)}봉 → {bad_ohlc[:3]}')

        # 봉간 급변동. 30분봉에서 ±5% 넘는 건 ETF 로선 이례적이다.
        jumps = []
        for i in range(1, len(rows)):
            p0 = float(rows[i - 1]['close'] or 0)
            p1 = float(rows[i]['close'] or 0)
            if p0 > 0:
                chg = (p1 - p0) / p0
                if abs(chg) > 0.05:
                    jumps.append((str(rows[i]['datetime']), round(chg * 100, 2)))
        if jumps:
            warn(f'{code}: 봉간 ±5% 초과 변동 {len(jumps)}건 → {jumps[:5]}')
        else:
            print(f'  {code}: 급변동 없음 (봉간 ±5% 이내)')

        px = [float(r['close']) for r in rows]
        print(f"  {code}: 종가 범위 {min(px):,.0f} ~ {max(px):,.0f} "
              f"(최종 {px[-1]:,.0f})")


def sec_c(rows_map: dict, code_a: str, code_b: str):
    print('\n[C] 정·역 상관 (가장 강력한 검증)')
    a, b = rows_map[code_a], rows_map[code_b]
    # 시각 교집합으로 맞춘다
    ma = {str(r['datetime']): float(r['close']) for r in a}
    mb = {str(r['datetime']): float(r['close']) for r in b}
    common = sorted(set(ma) & set(mb))
    print(f"  공통 봉 {len(common)}개 (A {len(ma)} / B {len(mb)})")
    if len(common) < 30:
        warn(f'공통 봉이 {len(common)}개뿐 — 두 종목 구간이 어긋나 있다')
        return

    ra, rb = [], []
    for i in range(1, len(common)):
        p0a, p1a = ma[common[i - 1]], ma[common[i]]
        p0b, p1b = mb[common[i - 1]], mb[common[i]]
        if p0a > 0 and p0b > 0:
            ra.append((p1a - p0a) / p0a)
            rb.append((p1b - p0b) / p0b)

    n = len(ra)
    mean_a, mean_b = sum(ra) / n, sum(rb) / n
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(ra, rb)) / n
    sd_a = (sum((x - mean_a) ** 2 for x in ra) / n) ** 0.5
    sd_b = (sum((y - mean_b) ** 2 for y in rb) / n) ** 0.5
    corr = cov / (sd_a * sd_b) if sd_a > 0 and sd_b > 0 else 0.0

    print(f"  봉별 수익률 상관계수 = {corr:+.4f}")
    if corr > -0.90:
        warn(f'인버스인데 상관계수가 {corr:+.4f} — 정상이면 -0.95 이하여야 한다. '
             f'데이터가 섞였거나 한쪽이 깨졌다.')
    else:
        print('  → 정상 (인버스 관계 확인)')


def sec_d(rows_map: dict):
    print('\n[D] Buy&Hold 검증')
    for code, rows in rows_map.items():
        if len(rows) < 2:
            continue
        first = float(rows[0].get('open') or rows[0].get('close') or 0)
        last = float(rows[-1]['close'])
        bh = (last - first) / first if first > 0 else 0.0
        days = len({str(r['datetime'])[:10] for r in rows})
        print(f"  {code}: {first:,.0f} → {last:,.0f} = {bh:+.2%} ({days}영업일)")

        # 현실성: ETF 가 20영업일에 ±30% 넘게 움직이는 건 사실상 없다
        if days > 0:
            per_20d = abs(bh) * (20 / days)
            if per_20d > 0.30:
                warn(f'{code}: 20영업일 환산 {per_20d:+.1%} — ETF 로선 비현실적. '
                     f'가격 데이터를 의심해야 한다.')


def sec_e(rows_map: dict):
    print('\n[E] 지표 컬럼 건전성')
    key_cols = ['macd_g_cross_n', 'obv_g_cross_n', 'macd', 'macd_s',
                'obv', 'obv_signal', 'rsi', 'atr', 'ema20', 'ema60',
                'bb_upper', 'bb_mid', 'recent_high', 'bb_mid_breakout']
    for code, rows in rows_map.items():
        if not rows:
            continue
        print(f"  {code}:")
        for col in key_cols:
            vals = [r.get(col) for r in rows]
            nulls = sum(1 for v in vals if v is None)
            zeros = sum(1 for v in vals
                        if v is not None and str(v) in ('0', '0.0', '0.00000000'))
            if col.endswith('_cross_n'):
                dist = Counter(str(v) for v in vals)
                top = dict(dist.most_common(4))
                g_cnt = dist.get('G', 0)
                print(f"    {col:<18} 분포={top}")
                if g_cnt == 0:
                    warn(f"{code}.{col}: 'G' 가 한 건도 없다 → "
                         f"golden 모드 신호가 영원히 안 뜬다. "
                         f"String 컬럼에 fillna(0.0) 이 들어갔는지 확인할 것.")
            else:
                nz_ratio = (len(vals) - nulls - zeros) / len(vals)
                flag = '' if nz_ratio > 0.5 else '  ← 대부분 0/NULL'
                print(f"    {col:<18} NULL={nulls:<5} 0값={zeros:<5} "
                      f"유효={nz_ratio:.0%}{flag}")
                if nz_ratio < 0.5:
                    warn(f'{code}.{col}: 유효값이 {nz_ratio:.0%} 뿐 — 지표 미계산 의심')


def sec_f(session, rows_map: dict, code_a: str, code_b: str):
    print('\n[F] 매수신호 재현 (KospiStrategy1 실제 호출)')
    ui = sim.user_info(session)

    presets = [
        ('전체 ON (운영 기본)', dict()),
        ('MACD-golden/OBV-off · 필터 최소',
         dict(macd_signal_mode='golden', obv_signal_mode='off',
              enable_bb_upper_filter=False, enable_vol_avg_filter=False,
              enable_regime_gate=False, enable_atr_filter=False,
              enable_vol_limit_filter=False)),
        ('core 신호 OFF (필터만)',
         dict(macd_signal_mode='off', obv_signal_mode='off')),
    ]

    for name, kw in presets:
        print(f"  · {name}")
        for code in (code_a, code_b):
            rows = list(rows_map[code])
            if len(rows) < 3:
                continue
            st = sim.build_strategy(**kw)
            KisBacktester(strategy=st).enrich_rows(rows)
            hits = 0
            for i in range(1, len(rows)):
                res = st.get_action_with_prev(
                    'watch', UserCoinInfo.from_dict(rows[i - 1]),
                    UserCoinInfo.from_dict(rows[i]), ui)
                name_ = res.get('action_type', 'HOLD') if isinstance(res, dict) \
                    else getattr(res, 'name', '')
                if name_.startswith('BUY'):
                    hits += 1
            pct = hits / (len(rows) - 1)
            print(f"      {code}: {hits}회 / {len(rows) - 1}봉 ({pct:.1%})")
            if hits == 0:
                warn(f'{code} [{name}]: 매수신호 0회 — 이 설정으로는 그리드가 무의미하다')


# ──────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description='trade_candle_30m 데이터 진단')
    ap.add_argument('--start', help='시작일 YYYY-MM-DD')
    ap.add_argument('--end', help='종료일 YYYY-MM-DD')
    args = ap.parse_args()

    session = dbConn.get_session()
    try:
        rows_map = {
            sim.CODE_A: sim.load_rows(session, sim.CODE_A, args.start, args.end),
            sim.CODE_B: sim.load_rows(session, sim.CODE_B, args.start, args.end),
        }

        print('=' * 72)
        print('trade_candle_30m 데이터 진단')
        print('=' * 72)

        sec_a(rows_map)
        sec_b(rows_map)
        sec_c(rows_map, sim.CODE_A, sim.CODE_B)
        sec_d(rows_map)
        sec_e(rows_map)
        sec_f(session, rows_map, sim.CODE_A, sim.CODE_B)

        print()
        print('=' * 72)
        if ISSUES:
            print(f'발견된 문제 {len(ISSUES)}건')
            for i, m in enumerate(ISSUES, 1):
                print(f'  {i}. {m}')
            print()
            print('→ 이 문제들을 먼저 해결하기 전에는 최적화 결과를 신뢰할 수 없다.')
        else:
            print('데이터 이상 없음. 최적화 결과 해석 가능.')
        print('=' * 72)
    finally:
        session.remove()


if __name__ == '__main__':
    main()
