"""
M3 교대매매(시나리오 1) 옵션 grid search.

trade_candle_30m 30분봉을 고정하고, 매수신호 판정 파라미터
(KospiStrategy1 필드) + confirm_bars 조합을 바꿔가며 시뮬레이션한다.

순위 기준
    사용자 선택: **총수익률 + MDD 를 같이 본다** → Calmar(총수익률 / MDD).
    항상 포지션을 들고 있는 전략이라 PF 만 보면 하방 리스크가 안 보인다.
    동률이면 총수익률 → 거래 수 순.

    MDD=0(무손실)인 조합은 Calmar 가 inf 가 되는데, 대개 거래 1~2건짜리
    표본부족이다. MIN_TRADES 미만은 순위에서 제외한다.

사용
    poetry run python -m app.test.optimize_m3_options
    poetry run python -m app.test.optimize_m3_options --quick
    poetry run python -m app.test.optimize_m3_options --start 2026-06-01 --top 30
    poetry run python -m app.test.optimize_m3_options --sort return   # 수익률 기준

캐시
    sim_m3_alternate._row_cache 가 DB 조회 결과를 들고 있어 조합 간 재사용된다.
    조합마다 DB 를 다시 읽으면 수백 쿼리가 나간다.
"""
import argparse
import itertools
import time

from app.config.database import dbConn
from app.test import sim_m3_alternate as sim
from stock_shared.strategy.m3_alternate import ScoreConfig

# 이보다 적으면 지표가 표본부족으로 왜곡되므로 순위 산정에서 제외
MIN_TRADES = 5


def _num(v, big=999.0):
    """'inf' 문자열을 큰 상수로 바꿔 정렬 가능하게."""
    if isinstance(v, str):
        return big if v == 'inf' else 0.0
    return float(v)


# ──────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════
# 30분봉 스케일 보정
#
#  KospiStrategy1 의 파라미터는 두 종류다.
#
#  (1) 봉 개수 파라미터 — vol_ma_window / regime_window / delay_date /
#      max_hold_bars 등. 코드는 '봉 N개' 로 동작하므로 타임프레임과 무관하게
#      정상 작동한다. 다만 값 자체가 일봉에서 격자탐색으로 찾은 것이라
#      30분봉 최적값이라는 보장이 없다 → **그리드에 넣어 다시 찾는다**.
#
#  (2) 크기(%) 파라미터 — atr_ratio_min / dip_from_high_* / stop_loss_pct 등.
#      이건 봉 길이에 직접 비례한다. 30분봉 한 개의 변동폭은 일봉의 1/5~1/6 이라
#      일봉용 임계값을 그대로 쓰면 **게이트가 영구히 닫힌다**.
#
#      실측(237350, 2026-08-12 14:30봉):
#          atr 678.68 / close 82,450 → atr_ratio = 0.82%
#          atr_ratio_min = 5% → is_atr_ok 가 항상 False → 매수신호 0건
#          dip_from_high = -1.38% (recent_high 83,605) → min 3% 미달 → dip 점수 상시 0
#
#      → 아래 값으로 30분봉 스케일에 맞춰 낮춘다.
#        (그래도 최적값은 모르므로 여러 후보를 그리드에 둔다)
# ══════════════════════════════════════════════════════════════
ATR_MIN_30M = [0.0, 0.003, 0.006, 0.010]      # 0=필터 무력화, 실측 0.82% 전후
DIP_MIN_30M = [0.002, 0.005]                  # 일봉 3% → 30분봉 0.2~0.5%
DIP_FULL_30M = 0.02                           # 일봉 15% → 30분봉 2%


def build_grid(quick: bool = False) -> list:
    """(라벨, confirm_bars, strategy_kwargs) 튜플 리스트."""
    if quick:
        confirm_list = [2]
        macd_list = ['slope', 'golden']
        obv_list = ['golden', 'off']
        ma20_list = ['off']
        filter_list = [
            # (macd, rsi, bb_upper, vol_avg, regime, atr, vol_limit)
            (True, True, True, True, True, True, True),
            (True, True, True, False, False, False, False),
        ]
        rsi_ob_list = [70]
        atr_min_list = [0.006]
        regime_win_list = [90]
        vol_win_list = [20]
    else:
        # 휩쏘 방어 강도. 1=즉시, 2=사용자 요청 기본, 3=더 보수적
        confirm_list = [1, 2, 3]
        macd_list = ['off', 'golden', 'slope']
        obv_list = ['off', 'golden', 'slope']
        ma20_list = ['off', 'slope']
        # 필터 프리셋. 30분봉은 일봉보다 신호가 잦아 필터를 다 켜면
        # 교대가 거의 안 일어나고, 다 끄면 휩쏘가 심해진다 → 중간 프리셋을 둔다.
        filter_list = [
            # (macd, rsi, bb_upper, vol_avg, regime, atr, vol_limit)
            (True,  True,  True,  True,  True,  True,  True),   # 전체 ON (운영 기본)
            (True,  True,  True,  True,  True,  False, False),  # ATR/거래량하한 OFF
            (True,  True,  True,  False, True,  False, False),  # + 평균거래량 OFF
            (True,  True,  False, False, True,  False, False),  # + BB상단 OFF
            (True,  True,  False, False, False, False, False),  # 국면게이트까지 OFF
            (False, False, False, False, False, False, False),  # 전체 OFF (core 신호만)
        ]
        rsi_ob_list = [65, 70, 75]
        # 30분봉 스케일 ATR 하한 (일봉용 5% 는 항상 차단되므로 후보에서 제외)
        atr_min_list = ATR_MIN_30M
        # 봉 개수 파라미터 — 일봉 튜닝값 그대로 vs 30분봉용 축소/확대
        regime_win_list = [30, 90, 180]     # 90봉 = 7영업일. 일봉 90봉과 의미가 다르다
        vol_win_list = [13, 20, 39]         # 13봉=1일, 39봉=3일

    combos = []
    for cb, macd, obv, ma20, filt, rsi_ob, atr_min, rw, vw in itertools.product(
            confirm_list, macd_list, obv_list, ma20_list, filter_list, rsi_ob_list,
            atr_min_list, regime_win_list, vol_win_list):

        f_macd, f_rsi, f_bb, f_vol, f_reg, f_atr, f_vlim = filt

        # ── 무의미한 조합 제거 (같은 결과를 여러 번 돌리는 낭비 방지) ──
        # 지난 실행에서 상위 18개가 수치까지 동일했던 건 이런 중복 때문이다.
        if not f_rsi and rsi_ob != rsi_ob_list[0]:
            continue
        if not f_atr and atr_min != atr_min_list[0]:
            continue                        # ATR 필터 OFF 면 하한값 무의미
        if not f_reg and rw != regime_win_list[0]:
            continue                        # 국면게이트 OFF 면 윈도우 무의미
        if not f_vol and vw != vol_win_list[0]:
            continue                        # 평균거래량 필터 OFF 면 윈도우 무의미

        label = (f"CB{cb}_MACD-{macd}_OBV-{obv}_MA20-{ma20}_"
                 f"F{int(f_macd)}{int(f_rsi)}{int(f_bb)}{int(f_vol)}"
                 f"{int(f_reg)}{int(f_atr)}{int(f_vlim)}_RSI{rsi_ob}"
                 f"_ATR{atr_min:.3f}_RW{rw}_VW{vw}")

        kwargs = dict(
            macd_signal_mode=macd,
            obv_signal_mode=obv,
            ma20_signal_mode=ma20,
            enable_macd_filter=f_macd,
            enable_rsi_filter=f_rsi,
            enable_bb_upper_filter=f_bb,
            enable_vol_avg_filter=f_vol,
            enable_regime_gate=f_reg,
            # ── 30분봉 스케일 보정 ──
            atr_ratio_min=atr_min,
            atr_ratio_full_score=max(atr_min * 2, 0.012),
            dip_from_high_min_pct=DIP_MIN_30M[0],
            dip_from_high_full_pct=DIP_FULL_30M,
            regime_window=rw,
            vol_ma_window=vw,
            enable_atr_filter=f_atr,
            enable_vol_limit_filter=f_vlim,
            rsi_overbought=rsi_ob,
        )
        combos.append((label, cb, kwargs))
    return combos


# ──────────────────────────────────────────────────────────────
SORT_KEYS = {
    # 사용자 선택 기본값: 총수익률 + MDD → Calmar
    'calmar': lambda r: (_num(r['calmar']), r['total_return'], r['trades']),
    'return': lambda r: (r['total_return'], -r['mdd'], r['trades']),
    'pf':     lambda r: (_num(r['profit_factor']), r['total_return']),
    'mdd':    lambda r: (-r['mdd'], r['total_return']),
}


def main():
    ap = argparse.ArgumentParser(description='M3 교대매매 옵션 grid search')
    ap.add_argument('--quick', action='store_true', help='축소 그리드(스모크 테스트)')
    ap.add_argument('--start', help='시작일 YYYY-MM-DD')
    ap.add_argument('--end', help='종료일 YYYY-MM-DD')
    ap.add_argument('--fee', type=float, default=0.0015, help='편도 수수료율')
    ap.add_argument('--slippage', type=float, default=0.0, help='편도 슬리피지율')
    ap.add_argument('--top', type=int, default=20, help='출력할 상위 조합 수')
    ap.add_argument('--sort', choices=list(SORT_KEYS), default='calmar',
                    help='순위 기준 (기본 calmar = 총수익률/MDD)')
    ap.add_argument('--min-trades', type=int, default=MIN_TRADES,
                    help='이보다 적은 거래 수는 순위 제외')
    ap.add_argument('--score-original', action='store_true',
                    help='score 가중치를 매수추천배치 원본으로')
    args = ap.parse_args()

    grid = build_grid(quick=args.quick)
    sc = ScoreConfig(w_tech=0.5, w_fund=0.3, w_liq=0.2) if args.score_original else None

    session = dbConn.get_session()
    try:
        # 데이터 현황 먼저
        for code in (sim.CODE_A, sim.CODE_B):
            cnt = sim._dao.count_by_coin(session, code)
            b = sim._dao.select_bounds(session, code)
            print(f"[데이터] {code}: {cnt}봉 ({b['first']} ~ {b['last']})")

        print(f"[그리드] {len(grid)} 조합 · sort={args.sort} · "
              f"min_trades={args.min_trades}")
        print()

        results = []
        t0 = time.time()
        for i, (label, cb, kwargs) in enumerate(grid, 1):
            try:
                res = sim.run_once(session, strategy_kwargs=kwargs, confirm_bars=cb,
                                   fee_rate=args.fee, slippage=args.slippage,
                                   score_config=sc, start=args.start, end=args.end)
            except Exception as e:                       # noqa: BLE001
                print(f"  [{i}/{len(grid)}] {label} 실패: {type(e).__name__}: {e}")
                continue
            res['label'] = label
            results.append(res)

            if i % 50 == 0 or i == len(grid):
                el = time.time() - t0
                print(f"  진행 {i}/{len(grid)} · {el:.1f}s "
                      f"({el / i:.2f}s/조합)")

        if not results:
            print('결과 없음.')
            return

        eligible = [r for r in results if r['trades'] >= args.min_trades]
        excluded = len(results) - len(eligible)
        if not eligible:
            print(f"\n⚠ 거래 {args.min_trades}건 이상인 조합이 없다. "
                  f"--min-trades 를 낮추거나 데이터 구간을 늘려야 한다.")
            eligible = results

        eligible.sort(key=SORT_KEYS[args.sort], reverse=True)

        bh = max(results[0]['bh_a'], results[0]['bh_b'])
        print()
        print('=' * 112)
        print(f"상위 {min(args.top, len(eligible))}개 조합  "
              f"(전체 {len(results)} · 표본부족 제외 {excluded} · "
              f"벤치마크 최선 Buy&Hold {bh:+.2%})")
        print('=' * 112)
        print(f"{'#':>3} {'조합':<52} {'교대':>4} {'수익률':>9} {'MDD':>8} "
              f"{'Calmar':>8} {'승률':>7} {'PF':>7}")
        print('-' * 112)
        for i, r in enumerate(eligible[:args.top], 1):
            print(f"{i:>3} {r['label']:<52} {r['trades']:>4} "
                  f"{r['total_return']:>+8.2%} {r['mdd']:>7.2%} "
                  f"{str(r['calmar']):>8} {r['win_rate']:>6.1%} "
                  f"{str(r['profit_factor']):>7}")
        print('-' * 112)

        best = eligible[0]
        print()
        print('▶ 최적 조합 상세')
        print(f"  {best['label']}")
        print(f"  교대 {best['trades']}회 · 수익률 {best['total_return']:+.2%} · "
              f"MDD {best['mdd']:.2%} · Calmar {best['calmar']}")
        print(f"  vs 최선 Buy&Hold({bh:+.2%}) → "
              f"{best['total_return'] - bh:+.2%}")
        print()
        print('  재현 명령:')
        cb = best['label'].split('_')[0][2:]
        print(f"    poetry run python -m app.test.sim_m3_alternate "
              f"--confirm {cb} --verbose")
    finally:
        session.remove()


if __name__ == '__main__':
    main()
