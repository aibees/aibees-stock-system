"""
trade_buy_target_stock(매수추천 누적) 기반 실전 시뮬레이션. 매도판단 = KospiStrategy1.

정책:
  - START_DATE 부터 하루씩 진행. 동시 보유 1종목, 전량매수/전량매도.
  - 대기(무포지션): 당일(ymd) 매수추천이 있으면 '1순위(rank_no)' 종목을 당일 종가에 매수.
                   추천 없으면 pass.
  - 보유중: 매일 KospiStrategy1.get_action_in_active 로 매도판단. SELL 계열이면 당일 종가 매도.
  - 매도한 날은 재매수 안 함. 다음날부터 다시 추천 1순위 탐색. 반복.
  - 체결가: 매수·매도 모두 '당일 종가'.
  - 포지션 상태(entry_price/entry_atr/peak/bars_held/bars_since_peak) 갱신 규칙은
    KisBacktester 와 동일.

사전조건:
  후보 종목 캔들이 trade_candle_data 에 적재돼 있어야 함
  (app.test.collect_buy_target_backfill 로 백필).

사용:
    poetry run python -m app.test.sim_buy_target
    poetry run python -m app.test.sim_buy_target 2026-04-01 2026-07-22
"""
import sys

from sqlalchemy import text

from app.config.database import dbConn
from stock_shared.dao.tradeCandleDataDao import TradeCandleDataDao
from stock_shared.vo.userCoinInfo import UserCoinInfo
from app.domain.dto.userOptionMeta import UserOptionMeta
from app.batches.services.userService import UserService
from app.ext_services.kis.component.KospiStrategy1 import KospiStrategy1
from app.ext_services.kis.component.KisBacktester import KisBacktester
from app.ext_services.StockStrategy import Action

# ══════════════════════════════════════════════════════════════════
# 설정
# ══════════════════════════════════════════════════════════════════
START_DATE = '2026-04-01'
END_DATE   = None          # None = 데이터 마지막 날까지
INIT_CASH  = 1_000_000
FEE_RATE   = 0.0011        # 편도 수수료+세금 근사 (요약 수익률용, 왕복 2배)
SAVE_PLOT  = True          # 결과 그래프(잔액곡선) PNG 저장
SAVE_TABLE = True          # 결과 매매로그 '표' 이미지 PNG 저장
PLOT_DIR   = '.'           # 이미지 저장 폴더

# ── 진입 규칙 ────────────────────────────────────────────────────
# ④ 종목 선택: '그날' 추천 중 '과열 최저'(당일 등락률 rate 가장 낮은) 종목.
#    ★ 당일 추천만 후보. 지나간 추천은 폐기(다음날부터는 그날 추천을 새로 봄).
# A: 매수 체결 시점
ENTRY_PRICE = 'next_open'  # 'close'(추천일 종가) | 'next_open'(다음 거래일 시가, 현실적)
# 갭업 추격 회피: next_open 일 때, 다음날 시가가 추천일 종가보다 높으면(급등 추격) 스킵.
SKIP_GAPUP  = False
# ══════════════════════════════════════════════════════════════════

session = dbConn.get_session()
daoImpl = TradeCandleDataDao()
userServiceImpl = UserService()

SELL_ACTIONS = {Action.SELL_PROFIT, Action.SELL_STOP_LOSS, Action.SELL_STOP_PROFIT,
                Action.SELL_TRAIL, Action.SELL_TIME}

_candle_cache = {}


def _user_info() -> UserOptionMeta:
    try:
        return userServiceImpl.get_user_options(session)
    except Exception:
        ui = UserOptionMeta()
        ui.vol_surge = 3.0
        ui.delay_date = 5
        ui.macd_recent_day = 20
        ui.bb_over_recent_day = 7
        return ui


def _trading_days(start: str, end: str = None) -> list:
    """trade_candle_data 에 존재하는 거래일(YYYY-MM-DD) 오름차순."""
    sql = "SELECT DISTINCT datetime FROM trade_candle_data WHERE datetime >= :s AND coin IN (SELECT ms.stock_code FROM master_stock ms WHERE ms.stock_type = 'KOSPI')"
    p = {'s': start + ' 00:00:00'}
    if end:
        sql += " AND datetime <= :e"
        p['e'] = end + ' 23:59:59'
    sql += " ORDER BY datetime"
    return [r[0][:10] for r in session.execute(text(sql), p).all()]


def _parse_rate(s) -> float:
    """'12.5%' → 12.5. 파싱 실패/None 은 inf(과열 최고로 취급 → 후순위)."""
    if s is None:
        return float('inf')
    try:
        return float(str(s).replace('%', '').strip())
    except Exception:
        return float('inf')


def _reco_by_day(start: str, end: str = None) -> dict:
    """ymd -> [(stock_code, rate_str), ...] '과열 최저'(당일 등락률 오름차순) 순."""
    sql = "SELECT ymd, stock_code, rate FROM trade_buy_target_stock WHERE ymd >= :s"
    p = {'s': start.replace('-', '')}
    if end:
        sql += " AND ymd <= :e"
        p['e'] = end.replace('-', '')
    tmp = {}
    for ymd, code, rate in session.execute(text(sql), p).all():
        tmp.setdefault(ymd, []).append((_parse_rate(rate), code, rate))
    return {ymd: [(c, r) for _, c, r in sorted(lst, key=lambda x: x[0])]
            for ymd, lst in tmp.items()}


def _name_map() -> dict:
    """stock_code -> stock_name (trade_buy_target_stock 에 저장된 이름)."""
    try:
        rows = session.execute(text(
            "SELECT DISTINCT stock_code, stock_name FROM trade_buy_target_stock")).all()
        return {c: (n or '') for c, n in rows}
    except Exception:
        return {}


def _set_kor_font():
    """한글 폰트 설정(있으면). macOS=AppleGothic / Linux=NanumGothic 등."""
    import matplotlib
    from matplotlib import font_manager as fm
    avail = {f.name for f in fm.fontManager.ttflist}
    for c in ('AppleGothic', 'Malgun Gothic', 'NanumGothic', 'NanumitchoGothic',
              'Noto Sans CJK KR', 'Noto Sans KR', 'UnDotum'):
        if c in avail:
            matplotlib.rcParams['font.family'] = c
            break
    matplotlib.rcParams['axes.unicode_minus'] = False


def _candles(code: str):
    """(rows_list, {date: (idx, row)}) 캐시 로드."""
    if code not in _candle_cache:
        rows = daoImpl.select_candle_data(session, {'coin_code': code})
        by_date = {r['datetime'][:10]: (i, r) for i, r in enumerate(rows)}
        _candle_cache[code] = (rows, by_date)
    return _candle_cache[code]


def run(start: str = START_DATE, end: str = END_DATE,
        init_cash: int = INIT_CASH, fee_rate: float = FEE_RATE) -> dict:
    strategy = KospiStrategy1()
    ui = _user_info()

    days = _trading_days(start, end)
    if not days:
        print(f'거래일 데이터 없음: {start} ~ {end or "최근"} (trade_candle_data 확인)')
        return {}
    reco = _reco_by_day(start, end)
    names = _name_map()

    trades = []
    mode = 'FLAT'          # FLAT(대기) | PENDING(다음날 시가 체결 대기) | HOLD(보유)
    code = entry_price = entry_date = None
    pend_code = pend_ref = None

    def _open_position(c, row, price, date):
        """포지션 진입: ui 상태 세팅. price=체결가, date=체결일."""
        nonlocal code, entry_price, entry_date, mode
        cur = UserCoinInfo.from_dict(row)
        code = c
        entry_price = float(price)
        entry_date = date
        ui.has_position = True
        ui.avg_price = ui.entry_price = entry_price
        ui.entry_atr = float(cur.atr or 0)
        ui.peak_high = float(cur.high)
        ui.peak_close = float(cur.close)
        ui.bars_since_peak = 0
        ui.bars_held = 0
        mode = 'HOLD'

    for di, d in enumerate(days):
        ymd = d.replace('-', '')

        # ── 보유중: 매도판단 (매수/매도 같은 날 동시수행 안 함) ──────────
        if mode == 'HOLD':
            rows, by_date = _candles(code)
            if d not in by_date:
                continue  # 해당 종목 그날 미거래(휴장/데이터 없음) → 다음날
            idx, cur_row = by_date[d]
            prev_row = rows[idx - 1] if idx > 0 else rows[idx]
            cur = UserCoinInfo.from_dict(cur_row)
            prev = UserCoinInfo.from_dict(prev_row)

            # 포지션 상태 갱신 (KisBacktester 와 동일)
            prev_peak = ui.peak_high
            ui.peak_high = max(ui.peak_high, cur.high)
            ui.peak_close = max(ui.peak_close, cur.close)
            ui.bars_since_peak = 0 if ui.peak_high > prev_peak else ui.bars_since_peak + 1
            ui.bars_held += 1

            res = strategy.get_action_with_prev('active', prev, cur, ui)
            action = res.get('result_action') or Action[res.get('action_type', 'HOLD')]
            if action in SELL_ACTIONS:
                exit_price = float(cur.close)
                gross = (exit_price - entry_price) / entry_price if entry_price > 0 else 0.0
                trades.append({
                    'coin': code, 'stock_name': names.get(code, ''),
                    'entry_dt': entry_date, 'entry_price': entry_price,
                    'entry_action': 'BUY', 'exit_dt': d, 'exit_price': exit_price,
                    'exit_reason': action.name, 'bars_held': ui.bars_held,
                    'ret_gross': gross, 'ret_net': gross - 2 * fee_rate,
                })
                mode = 'FLAT'
                code = entry_price = entry_date = None
            continue  # 매도했든 아니든 그날은 재매수 안 함

        # ── 다음날 시가 체결 대기 (ENTRY_PRICE='next_open', 1일만 유효) ───
        if mode == 'PENDING':
            rows, by_date = _candles(pend_code)
            if d in by_date:
                idx, row = by_date[d]
                o_px = float(row['open'])
                if SKIP_GAPUP and o_px > pend_ref:      # 다음날 시가가 추천일 종가보다↑ → 추격 스킵
                    mode = 'FLAT'                       # 폐기 → 아래 FLAT 스캔(오늘 추천 새로)
                else:
                    _open_position(pend_code, row, o_px, d)  # 다음날 시가 매수
                    continue
            else:
                # 후보가 다음 거래일에 안 나옴(휴장/데이터 없음) → 폐기(당일 추천 새로 봄)
                mode = 'FLAT'

        # ── 대기(무포지션): '오늘' 추천 중 과열 최저 선택 ─────────────────
        #   당일 추천만 후보. 지나간 추천은 절대 안 봄.
        if mode == 'FLAT':
            cand = reco.get(ymd)
            if not cand:
                continue  # 오늘 추천 없음 → pass
            chosen = None
            for c, _rate in cand:            # 과열 낮은 순, 캔들 있는 첫 종목
                rows, by_date = _candles(c)
                if d in by_date:
                    chosen = (c, by_date[d][1])
                    break
            if not chosen:
                continue
            code_sel, cand_row = chosen
            if ENTRY_PRICE == 'next_open':
                pend_code = code_sel
                pend_ref = float(cand_row['close'])   # 추천일 종가(갭업 판정 기준)
                mode = 'PENDING'                      # 다음 거래일 시가에 체결
            else:
                _open_position(code_sel, cand_row, float(cand_row['close']), d)  # 당일 종가 매수
            continue

    # ── 종료 시 미청산 포지션 정리 (마지막날 종가) ────────────────────
    if mode == 'HOLD':
        rows, by_date = _candles(code)
        last_idx = by_date.get(days[-1], (len(rows) - 1, rows[-1]))[0]
        last_close = float(rows[last_idx]['close'])
        gross = (last_close - entry_price) / entry_price if entry_price > 0 else 0.0
        trades.append({
            'coin': code, 'stock_name': names.get(code, ''),
            'entry_dt': entry_date, 'entry_price': entry_price,
            'entry_action': 'BUY', 'exit_dt': days[-1], 'exit_price': last_close,
            'exit_reason': 'EOD', 'bars_held': ui.bars_held,
            'ret_gross': gross, 'ret_net': gross - 2 * fee_rate,
        })

    _report(strategy, start, days, trades, init_cash)
    tag = 'gapup' if (ENTRY_PRICE == 'next_open' and SKIP_GAPUP) else 'nogapskip'
    if SAVE_PLOT and trades:
        try:
            print(f'[그래프] {_plot_result(trades, init_cash, tag=tag)}')
        except Exception as e:
            print(f'[그래프] 생성 실패: {type(e).__name__}: {e}')
    if SAVE_TABLE and trades:
        try:
            print(f'[표] {_table_image(trades, strategy, init_cash, tag=tag)}')
        except Exception as e:
            print(f'[표] 생성 실패: {type(e).__name__}: {e}')
    return {'trades': trades}


def _plot_result(trades, init_cash=INIT_CASH, out_dir=PLOT_DIR, tag='') -> str:
    """결과 도표 PNG: (상)누적 잔액 곡선 + (하)거래별 손익%. summary 박스 포함."""
    import os
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    BUY_FEE = SELL_FEE = 0.0011
    cash = init_cash
    curve = [init_cash]
    rets, labels = [], []
    for t in trades:
        ep, xp = t['entry_price'], t['exit_price']
        sh = int(cash / (ep * (1 + BUY_FEE))) if ep > 0 else 0
        cash = cash - sh * ep * (1 + BUY_FEE) + sh * xp * (1 - SELL_FEE)
        curve.append(cash)
        rets.append(t['ret_net'] * 100)
        labels.append(f"{t['coin']}\n{t['entry_dt'][5:]}")
    s = KisBacktester()._summarize('SIM', trades)
    final_pct = (cash / init_cash - 1) * 100

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9),
                                   gridspec_kw={'height_ratios': [2, 1.4]})
    fig.suptitle(f'buy_target Simulation Result{(" - " + tag) if tag else ""}  '
                 f'(final {final_pct:+.1f}%)', fontsize=14, fontweight='bold')

    # (1) 누적 잔액 곡선
    x = list(range(len(curve)))
    ax1.plot(x, curve, marker='o', ms=5, color='#1f77b4', lw=1.6, zorder=3)
    ax1.axhline(init_cash, ls='--', color='gray', lw=1)
    ax1.fill_between(x, init_cash, curve, where=[c >= init_cash for c in curve],
                     color='tab:green', alpha=0.12)
    ax1.fill_between(x, init_cash, curve, where=[c < init_cash for c in curve],
                     color='tab:red', alpha=0.12)
    ax1.set_ylabel('Equity (KRW)')
    ax1.set_xlabel('Trade #')
    ax1.grid(alpha=0.25)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f'{v/1e6:.2f}M'))

    box = (f"trades {s['trades']}   win {s['win_rate']}%\n"
           f"total {s['total_return']:+.1f}%   PF {s['profit_factor']}\n"
           f"avg win {s['avg_win']:+.1f}%   avg loss {s['avg_loss']:+.1f}%\n"
           f"MDD {s['mdd']}%   avg {s['avg_bars']} bars")
    ax1.text(0.015, 0.97, box, transform=ax1.transAxes, va='top', ha='left',
             fontsize=10, family='monospace',
             bbox=dict(boxstyle='round', fc='white', ec='gray', alpha=0.9))

    # (2) 거래별 손익 %
    colors = ['tab:green' if r > 0 else 'tab:red' for r in rets]
    ax2.bar(range(len(rets)), rets, color=colors, alpha=0.85)
    ax2.axhline(0, color='black', lw=0.8)
    ax2.set_ylabel('Trade P&L (%)')
    ax2.set_xticks(range(len(rets)))
    ax2.set_xticklabels(labels, fontsize=7.5)
    for i, r in enumerate(rets):
        ax2.text(i, r + (1 if r >= 0 else -1), f'{r:+.0f}', ha='center',
                 va='bottom' if r >= 0 else 'top', fontsize=7.5)
    ax2.grid(alpha=0.25, axis='y')

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f'sim_result{("_" + tag) if tag else ""}.png')
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return os.path.abspath(path)


_REASON_KR = {'SELL_PROFIT': '익절', 'SELL_STOP_LOSS': '손절', 'SELL_STOP_PROFIT': '익절',
              'SELL_TRAIL': '트레일', 'SELL_TIME': '타임', 'EOD': '종료청산'}


def _table_image(trades, strategy, init_cash=INIT_CASH, out_dir=PLOT_DIR, tag='') -> str:
    """매매 로그를 '표'로 렌더한 PNG. (코드/종목명/매매일자/가격/사유/손익/잔액)"""
    import os
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    _set_kor_font()

    cols = ['#', '코드', '종목명', '매수일', '매수가', '매도일', '매도가',
            '사유', '봉', '손익%', '잔액']
    BUY_FEE = SELL_FEE = 0.0011
    cash = init_cash
    body, cell_colors = [], []
    for i, t in enumerate(trades, 1):
        ep, xp = t['entry_price'], t['exit_price']
        sh = int(cash / (ep * (1 + BUY_FEE))) if ep > 0 else 0
        cash = cash - sh * ep * (1 + BUY_FEE) + sh * xp * (1 - SELL_FEE)
        ret = t['ret_net'] * 100
        win = ret > 0
        body.append([
            str(i), t['coin'], t.get('stock_name', ''),
            t['entry_dt'], f"{ep:,.0f}", t['exit_dt'], f"{xp:,.0f}",
            _REASON_KR.get(t['exit_reason'], t['exit_reason']),
            str(t['bars_held']), f"{ret:+.2f}", f"{cash:,.0f}",
        ])
        base = '#e8f5e9' if win else '#fdecea'      # 승=연초록 / 패=연빨강
        row_c = [base] * len(cols)
        row_c[9] = '#c8e6c9' if win else '#f5c6cb'  # 손익% 강조
        cell_colors.append(row_c)

    summary = KisBacktester(strategy=strategy)._summarize('SIM', trades)
    final_pct = (cash / init_cash - 1) * 100

    n = len(body)
    fig, ax = plt.subplots(figsize=(13, 1.1 + 0.42 * (n + 1)))
    ax.axis('off')
    ax.set_title(
        f"buy_target 시뮬 매매로그{('  ['+tag+']') if tag else ''}   "
        f"({summary['trades']}건 · 승률 {summary['win_rate']}% · "
        f"총 {final_pct:+.1f}% · PF {summary['profit_factor']} · MDD {summary['mdd']}%)",
        fontsize=12, fontweight='bold', pad=14)

    tbl = ax.table(cellText=body, colLabels=cols, cellColours=cell_colors,
                   cellLoc='center', loc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.35)
    # 헤더 스타일
    for j in range(len(cols)):
        c = tbl[(0, j)]
        c.set_facecolor('#37474f')
        c.set_text_props(color='white', fontweight='bold')
    # 종목명 좌측정렬 + 열폭
    widths = [0.035, 0.06, 0.13, 0.085, 0.085, 0.085, 0.085, 0.07, 0.035, 0.07, 0.11]
    for j, w in enumerate(widths):
        for r in range(n + 1):
            tbl[(r, j)].set_width(w)
    for r in range(1, n + 1):
        tbl[(r, 2)].set_text_props(ha='left')

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f'sim_table{("_" + tag) if tag else ""}.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return os.path.abspath(path)


def _report(strategy, start, days, trades, init_cash):
    summary = KisBacktester(strategy=strategy)._summarize('SIM', trades)
    print('===== buy_target 실전 시뮬 (KospiStrategy1 매도) =====')
    print(f'기간: {days[0]} ~ {days[-1]} ({len(days)}거래일) | 1포지션 전량매매')
    print(f'선택: 당일추천만·과열최저(rate↓) | 체결: 매수={ENTRY_PRICE}'
          f'{"(갭업스킵)" if (ENTRY_PRICE=="next_open" and SKIP_GAPUP) else ""}, 매도=당일종가')
    for k in ('trades', 'win_rate', 'total_return', 'avg_ret', 'avg_win', 'avg_loss',
              'profit_factor', 'mdd', 'avg_bars', 'exit_breakdown'):
        print(f'  {k:14}: {summary.get(k)}')

    print(f'--- 매매 {len(trades)}건 ---')
    BUY_FEE = SELL_FEE = 0.0011
    cash = init_cash
    for t in trades:
        ep, xp = t['entry_price'], t['exit_price']
        shares = int(cash / (ep * (1 + BUY_FEE))) if ep > 0 else 0
        buy_cost = shares * ep * (1 + BUY_FEE)
        sell_recv = shares * xp * (1 - SELL_FEE)
        cash = cash - buy_cost + sell_recv
        print(f"{t['entry_dt']} BUY {t['coin']} @{ep:.0f} x{shares} -> "
              f"{t['exit_dt']} {t['exit_reason']} @{xp:.0f} "
              f"| {t['bars_held']}bars | {t['ret_net'] * 100:+.2f}% → 잔액 {cash:,.0f}원")
    print(f'\n[가상자금] 시작 {init_cash:,}원 → 최종 {cash:,.0f}원 '
          f'({cash - init_cash:+,.0f}원 / {(cash / init_cash - 1) * 100:+.2f}%)')


if __name__ == '__main__':
    args = sys.argv[1:]
    s = args[0] if len(args) >= 1 else START_DATE
    e = args[1] if len(args) >= 2 else END_DATE
    run(s, e)
