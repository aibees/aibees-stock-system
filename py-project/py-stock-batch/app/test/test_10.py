"""
KospiStrategy2 단일 종목 백테스트 러너.

사용법:
    STOCK_CODE 만 바꿔가며 실행하면 trade_candle_data 에 적재된 해당 종목
    데이터로 KospiStrategy2(HMA + MACD + OBV + 컨펌캔들) 백테스트가 돌아간다.

    # 프로젝트 루트에서
    python -m app.test.test_10
    # 또는 코드에서
    from app.test.test_10 import run
    run('005930')

사전조건:
    trade_candle_data 에 종목 지표가 적재돼 있어야 함(test_5.test_backtest_insert 등).

튜닝(ablation):
    STRATEGY_OVERRIDES 딕셔너리에 원하는 속성만 넣으면 전략 인스턴스에 덮어써진다.
    예) 컨펌캔들 끄고 기여도 보기 → {'enable_confirm_candle': False}
        종가강도 기준 완화        → {'confirm_clv_min': 0.5}
        신호 모드 변경            → {'macd_signal_mode': 'slope'}
"""
import pprint

from app.config.database import dbConn
from stock_shared.dao.tradeCandleDataDao import TradeCandleDataDao
from stock_shared.dto.userOptionMeta import UserOptionMeta
from app.batches.services.userService import UserService
from stock_shared.strategy.kospi2 import KospiStrategy2
from stock_shared.strategy.backtester import KisBacktester

# ══════════════════════════════════════════════════════════════════
# 여기만 바꾸면 됨
# ══════════════════════════════════════════════════════════════════
STOCK_CODE = '005930'      # ← 종목코드만 바꿔가며 실행
START_DATE = None          # 'YYYY-MM-DD' 또는 None(전체)
END_DATE   = None          # 'YYYY-MM-DD' 또는 None(전체)
FEE_RATE   = 0.0015        # 편도 수수료+세금 근사(왕복 2배 차감)
INIT_CASH  = 1_000_000     # 가상 자금

SAVE_PLOT  = True          # 백테스트 차트 PNG 저장 여부
PLOT_DIR   = '.'           # 차트 저장 폴더(기본: 실행 위치)

# 전략 파라미터 오버라이드(비우면 KospiStrategy2 기본값). ablation/튜닝용.
STRATEGY_OVERRIDES: dict = {
    # 'enable_confirm_candle': False,
    # 'confirm_clv_min': 0.5,
    # 'confirm_vol_mult': 1.5,
    # 'hma_signal_mode': 'above',
    # 'macd_signal_mode': 'slope',
    # 'obv_signal_mode': 'slope',
}
# ══════════════════════════════════════════════════════════════════

session = dbConn.get_session()
daoImpl = TradeCandleDataDao()
userServiceImpl = UserService()


def _user_info() -> UserOptionMeta:
    """user_options 조회 실패 시 최소 기본값으로 대체."""
    try:
        return userServiceImpl.get_user_options(session)
    except Exception:
        ui = UserOptionMeta()
        ui.vol_limit = 0
        ui.vol_surge = 3.0
        ui.delay_date = 5
        ui.macd_recent_day = 20
        ui.bb_over_recent_day = 7
        return ui


def _build_strategy() -> KospiStrategy2:
    s = KospiStrategy2()
    for attr, val in STRATEGY_OVERRIDES.items():
        if not hasattr(s, attr):
            print(f"[경고] 알 수 없는 전략 속성 무시: {attr}")
            continue
        setattr(s, attr, val)
    return s


def _plot(coin_code: str, rows: list, result: dict, out_dir: str = PLOT_DIR) -> str:
    """가격+HMA / MACD+signal / OBV+signal 3단 패널에 매수·매도 시점 표시 → PNG 저장.

    rows 는 bt.run_one() 이후 상태(hma 주입 완료)를 그대로 넘겨야 한다.
    """
    import os
    import matplotlib
    matplotlib.use('Agg')  # 화면 없는 환경에서도 파일 저장
    import matplotlib.pyplot as plt

    n = len(rows)
    x = list(range(n))
    dts = [r.get('datetime', '')[:10] for r in rows]
    def col(key):
        return [float(r[key]) if r.get(key) is not None else float('nan') for r in rows]

    close = col('close'); hma = col('hma')
    hma = [v if v and v > 0 else float('nan') for v in hma]  # warmup(0) 구간은 미표시
    macd = col('macd');   macd_s = col('macd_s')
    obv = col('obv');     obv_sig = col('obv_signal')

    # datetime → index 매핑(매매 마커 위치)
    dt2i = {r.get('datetime'): i for i, r in enumerate(rows)}
    def idx_of(dt):
        if dt in dt2i:
            return dt2i[dt]
        for i, r in enumerate(rows):           # 체결이 '다음 봉'이라 일치 안 하면 근접 탐색
            if r.get('datetime', '') >= dt:
                return i
        return None

    reason_color = {'SELL_PROFIT': 'tab:green', 'SELL_STOP_LOSS': 'tab:red',
                    'SELL_TRAIL': 'tab:orange', 'SELL_TIME': 'gray', 'EOD': 'black'}

    fig, (ax1, ax2, ax3) = plt.subplots(
        3, 1, figsize=(16, 10), sharex=True,
        gridspec_kw={'height_ratios': [3, 1.3, 1.3]})
    fig.suptitle(f'KospiStrategy2 backtest - {coin_code}  '
                 f'({result.get("trades", 0)} trades / win {result.get("win_rate", 0)}% '
                 f'/ return {result.get("total_return", 0):+.1f}%)', fontsize=13)

    # ── (1) 가격 + HMA + 매수/매도 ─────────────────────────────
    ax1.plot(x, close, color='#333', lw=1.0, label='Close')
    ax1.plot(x, hma, color='tab:blue', lw=1.3, label=f'HMA')
    for t in result.get('trade_list', []):
        ei, xi = idx_of(t['entry_dt']), idx_of(t['exit_dt'])
        if ei is not None:
            ax1.scatter(ei, close[ei], marker='^', s=90, color='tab:green',
                        zorder=5, edgecolors='white', linewidths=0.6)
        if xi is not None:
            ax1.scatter(xi, close[xi], marker='v', s=90,
                        color=reason_color.get(t['exit_reason'], 'black'),
                        zorder=5, edgecolors='white', linewidths=0.6)
        if ei is not None and xi is not None:
            win = t['ret_net'] > 0
            ax1.plot([ei, xi], [close[ei], close[xi]], ls='--', lw=0.8,
                     color=('tab:green' if win else 'tab:red'), alpha=0.5)
    ax1.set_ylabel('Price'); ax1.legend(loc='upper left', fontsize=9)
    ax1.grid(alpha=0.25)

    # ── (2) MACD ────────────────────────────────────────────────
    ax2.plot(x, macd, color='tab:blue', lw=1.0, label='MACD')
    ax2.plot(x, macd_s, color='tab:orange', lw=1.0, label='Signal')
    ax2.bar(x, [m - s for m, s in zip(macd, macd_s)], color='gray', alpha=0.35, width=1.0)
    ax2.axhline(0, color='black', lw=0.6)
    ax2.set_ylabel('MACD'); ax2.legend(loc='upper left', fontsize=8); ax2.grid(alpha=0.25)

    # ── (3) OBV ─────────────────────────────────────────────────
    ax3.plot(x, obv, color='tab:purple', lw=1.0, label='OBV')
    ax3.plot(x, obv_sig, color='tab:orange', lw=1.0, label='OBV signal')
    ax3.set_ylabel('OBV'); ax3.legend(loc='upper left', fontsize=8); ax3.grid(alpha=0.25)

    # x축 날짜 라벨(약 12개만)
    step = max(1, n // 12)
    ax3.set_xticks(x[::step])
    ax3.set_xticklabels(dts[::step], rotation=45, ha='right', fontsize=8)

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f'backtest_{coin_code}.png')
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
    return os.path.abspath(out_path)


def run(coin_code: str = STOCK_CODE,
        start_date: str = START_DATE, end_date: str = END_DATE,
        fee_rate: float = FEE_RATE, init_cash: int = INIT_CASH,
        save_plot: bool = SAVE_PLOT) -> dict:
    rows = daoImpl.select_candle_data(session, {
        'coin_code': coin_code, 'start_date': start_date, 'end_date': end_date,
    })
    if not rows:
        print(f'데이터 없음: {coin_code} (trade_candle_data 적재 확인)')
        return {}

    strategy = _build_strategy()
    bt = KisBacktester(strategy=strategy, fee_rate=fee_rate)
    result = bt.run_one(coin_code, rows, _user_info())

    ov = {k: v for k, v in STRATEGY_OVERRIDES.items()}
    print('===== KospiStrategy2 백테스트 =====')
    print(f'종목: {coin_code} | 봉수: {len(rows)} | 기간: {rows[0]["datetime"][:10]} ~ {rows[-1]["datetime"][:10]}')
    if ov:
        print(f'오버라이드: {ov}')
    summary = {k: v for k, v in result.items() if k != 'trade_list'}
    pprint.pprint(summary)
    print(f'--- 매매 {len(result["trade_list"])}건 ---')

    # 가상 자금 시뮬레이션(전량 매수/매도, 편도 0.11%, 정수 주)
    BUY_FEE = SELL_FEE = 0.0011
    cash = init_cash
    for t in result['trade_list']:
        entry_p, exit_p = t['entry_price'], t['exit_price']
        shares = int(cash / (entry_p * (1 + BUY_FEE))) if entry_p > 0 else 0
        buy_cost = shares * entry_p * (1 + BUY_FEE)
        sell_recv = shares * exit_p * (1 - SELL_FEE)
        cash = cash - buy_cost + sell_recv
        pnl = sell_recv - buy_cost
        print(f"{t['entry_dt'][:10]} {t['entry_action']} @{entry_p:.0f} x{shares}주 -> "
              f"{t['exit_dt'][:10]} {t['exit_reason']} @{exit_p:.0f} "
              f"| {t['bars_held']}bars | {t['ret_net'] * 100:+.2f}% "
              f"| 손익 {pnl:+,.0f}원 → 잔액 {cash:,.0f}원")

    profit = cash - init_cash
    print(f'\n[가상 자금] 시작 {init_cash:,}원 → 최종 {cash:,.0f}원 '
          f'({profit:+,.0f}원 / {(cash / init_cash - 1) * 100:+.2f}%)')

    # 차트 저장 (rows 는 run_one 에서 hma 주입 완료된 상태)
    if save_plot:
        try:
            path = _plot(coin_code, rows, result)
            print(f'[차트] {path}')
        except Exception as e:
            print(f'[차트] 생성 실패: {type(e).__name__}: {e}')
    return result


def diagnose(coin_code: str = STOCK_CODE, only_hma_upturn: bool = True,
             start_date: str = START_DATE, end_date: str = END_DATE) -> None:
    """HMA 저점 변곡(기울기 음→양) 봉마다 '어느 게이트가 진입을 막았는지' 출력.

    only_hma_upturn=False 로 두면 전 봉을 찍는다.
    현재 STRATEGY_OVERRIDES 설정 기준으로 판정하므로, 설정을 바꿔가며
    '이 조합이면 동그라미 지점을 잡는지'를 표로 확인할 수 있다.
    """
    from stock_shared.vo.userCoinInfo import UserCoinInfo
    rows = daoImpl.select_candle_data(session, {
        'coin_code': coin_code, 'start_date': start_date, 'end_date': end_date})
    if not rows:
        print(f'데이터 없음: {coin_code}')
        return

    strategy = _build_strategy()
    bt = KisBacktester(strategy=strategy, fee_rate=FEE_RATE)
    bt.run_one(coin_code, rows, _user_info())   # rows 에 hma/hma_slope/vol_avg 등 주입
    ui = _user_info()

    def _blocked_by(ind: dict) -> str:
        """게이트 통과 순서대로 첫 탈락 사유 반환(get_action_in_watch 와 동일 순서)."""
        if ind.get('is_fresh') != 'Y':
            missed = [k for k, on in (('hma', strategy.enable_hma_filter),
                                      ('macd', strategy.enable_macd_filter),
                                      ('obv', strategy.enable_obv_filter))
                      if on and ind.get(f'{k}_sig') != 'Y']
            return f"core AND 미충족({','.join(missed) or 'freshness'})"
        if strategy.enable_confirm_candle and ind.get('confirm_candle_ok') != 'Y':
            fail = [k for k, key in (('양봉', 'is_body_up'), ('거래량', 'is_vol_loaded'),
                                     ('종가강도', 'is_close_strong')) if ind.get(key) != 'Y']
            return f"컨펌캔들({','.join(fail)})"
        if strategy.enable_chegyul_filter and ind.get('is_chegyul_ok') != 'Y':
            return '체결강도'
        if strategy.enable_rsi_filter and ind.get('is_rsi_overbought') == 'Y':
            return 'RSI 과매수'
        if strategy.enable_bb_upper_filter and ind.get('is_under_bb_upper') != 'Y':
            return 'BB 상단'
        if strategy.enable_vol_avg_filter and ind.get('is_vol_above_avg') != 'Y':
            return '평균거래량'
        if getattr(strategy, 'enable_regime_gate', False) and ind.get('regime_gate') != 'Y':
            return f"레짐게이트({ind.get('regime','?')}/dt{ind.get('downtrend_ratio','?')})"
        return '-'

    print(f'===== 진입 진단 {coin_code} (설정: {STRATEGY_OVERRIDES or "기본값"}) =====')
    print(f"{'날짜':<12}{'action':<10}{'hma':<5}{'macd':<6}{'obv':<6}{'confirm':<9}{'fresh':<6}차단사유")
    hit = 0
    for i in range(1, len(rows)):
        cur_s = float(rows[i].get('hma_slope') or 0)
        prev_s = float(rows[i - 1].get('hma_slope') or 0)
        if only_hma_upturn and not (prev_s <= 0 < cur_s):
            continue
        prev = UserCoinInfo.from_dict(rows[i - 1])
        cur = UserCoinInfo.from_dict(rows[i])
        res = strategy.get_action_with_prev('watch', prev, cur, ui)
        ind = res.get('indicator', {})
        act = res.get('action_type', 'HOLD')
        blocked = '' if act.startswith('BUY') else _blocked_by(ind)
        hit += 1
        print(f"{rows[i]['datetime'][:10]:<12}{act:<10}"
              f"{ind.get('hma_sig','-'):<5}{ind.get('macd_sig','-'):<6}{ind.get('obv_sig','-'):<6}"
              f"{ind.get('confirm_candle_ok','-'):<9}{ind.get('is_fresh','-'):<6}{blocked}")
    print(f'--- HMA 상승변곡 봉 {hit}개 ---')


if __name__ == '__main__':
    import sys
    # python -m app.test.test_10 [run|diag] 종목코드
    args = sys.argv[1:]
    cmd = 'run'
    if args and args[0] in ('run', 'diag'):
        cmd, args = args[0], args[1:]
    code = args[0] if args else STOCK_CODE
    diagnose(code) if cmd == 'diag' else run(code)
