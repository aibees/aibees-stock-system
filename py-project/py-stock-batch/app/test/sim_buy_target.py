"""
trade_buy_target_stock(매수추천 누적) 기반 실전 시뮬레이션. 매도판단 = KospiStrategy1.

정책:
  - START_DATE 부터 하루씩 진행. 동시 보유 1종목, 전량매수/전량매도.
  - 대기(무포지션): 당일(ymd) 매수추천이 있으면 '1순위(rank_no)' 종목을 당일 종가에 매수.
                   추천 없으면 pass.
  - 보유중: 매일 KospiStrategy1.get_action_in_active 로 매도판단. SELL 계열이면 당일 종가 매도.
             진입일(체결일)에도 매도판단 수행(bars_held=0, peak 갱신 없이 1회).
  - 매도한 날은 재매수 안 함. 다음날부터 다시 추천 1순위 탐색. 반복.
  - 체결가: 매수·매도 모두 '당일 종가'.
  - 포지션 상태(entry_price/entry_atr/peak/bars_held/bars_since_peak) 갱신 규칙은
    KisBacktester 와 동일.

추천 소스 테이블 선택(2026-08-08 추가):
  운영 테이블(trade_buy_target_stock) 또는 오프라인 테스트 테이블
  (trade_buy_target_stock_test — app/test/run_test_buy_check.py 가 새 알고리즘으로
  채움) 중 어디서 '오늘 추천'을 읽을지 선택할 수 있다. --table both(기본)면 두 테이블
  각각으로 동일 기간을 시뮬레이션하고 결과를 나란히 비교(수치표 + 겹친 잔액곡선 그래프)한다.

사전조건:
  후보 종목 캔들이 trade_candle_data 에 적재돼 있어야 함
  (app.test.collect_buy_target_backfill 로 백필).
  --table test 또는 both 를 쓰려면 trade_buy_target_stock_test 에 데이터가 있어야
  함(app.test.run_test_buy_check 로 먼저 채워둘 것).

사용:
    poetry run python -m app.test.sim_buy_target                                   # 기본: 운영 vs 테스트 비교
    poetry run python -m app.test.sim_buy_target 2026-04-01 2026-07-22
    poetry run python -m app.test.sim_buy_target 2026-04-01 2026-07-22 --table prod  # 운영만(기존 동작)
    poetry run python -m app.test.sim_buy_target 2026-04-01 2026-07-22 --table test  # 테스트만
"""
from sqlalchemy import text

from app.config.database import dbConn
from stock_shared.dao.tradeCandleDataDao import TradeCandleDataDao
from stock_shared.vo.userCoinInfo import UserCoinInfo
from stock_shared.dto.userOptionMeta import UserOptionMeta
from app.batches.services.userService import UserService
from stock_shared.strategy.kospi1 import KospiStrategy1
from stock_shared.strategy.backtester import KisBacktester
from stock_shared.strategy.base import Action

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

# ── 추천 소스 테이블 ─────────────────────────────────────────────
TABLE_PROD  = 'trade_buy_target_stock'         # 운영(라이브 배치가 채움)
TABLE_TEST  = 'trade_buy_target_stock_test'    # 오프라인 테스트(run_test_buy_check.py 가 채움)
_ALLOWED_TABLES = (TABLE_PROD, TABLE_TEST)     # SQL에 직접 꽂으므로 화이트리스트로 방어
_TABLE_LABEL = {TABLE_PROD: 'prod', TABLE_TEST: 'test'}
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


def _reco_by_day(start: str, end: str = None, table: str = TABLE_PROD) -> dict:
    """ymd -> [(stock_code, rate_str, action_type), ...] '과열 최저'(당일 등락률 오름차순) 순.
    table: TABLE_PROD(운영) | TABLE_TEST(오프라인 테스트) — 화이트리스트 검증 후 SQL에 사용."""
    assert table in _ALLOWED_TABLES, f"허용되지 않은 테이블: {table}"
    sql = f"SELECT ymd, stock_code, rate, action_type FROM {table} WHERE ymd >= :s"
    p = {'s': start.replace('-', '')}
    if end:
        sql += " AND ymd <= :e"
        p['e'] = end.replace('-', '')
    tmp = {}
    for ymd, code, rate, action_type in session.execute(text(sql), p).all():
        tmp.setdefault(ymd, []).append((_parse_rate(rate), code, rate, action_type))
    return {ymd: [(c, r, a) for _, c, r, a in sorted(lst, key=lambda x: x[0])]
            for ymd, lst in tmp.items()}


def _buy_reason(code: str, ymd: str, action_type: str, rate) -> str:
    """매수 사유 요약. user_options 는 보통 macd/obv 신호를 'slope'(기울기) 모드로 쓰고 있어서
    (macd_cross/obv_cross 원본 컬럼은 '골든크로스' 여부만 담아 실제 신호를 못 읽는 경우가 많다)
    캔들에서 당일 vs 전봉 macd/obv 를 직접 비교해 기울기 신호를 판단한다."""
    rows, by_date = _candles(code)
    d = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"
    parts = [action_type or 'BUY']
    if d in by_date:
        idx, cur_row = by_date[d]
        if idx > 0:
            prev_row = rows[idx - 1]
            try:
                if float(cur_row.get('macd', 0)) > float(prev_row.get('macd', 0)):
                    parts.append('MACD↑')
                if float(cur_row.get('obv', 0)) > float(prev_row.get('obv', 0)):
                    parts.append('OBV↑')
            except (TypeError, ValueError):
                pass
        try:
            if float(cur_row.get('vol_surge_n', 0) or 0) > 0:
                parts.append('거래량급증')
        except (TypeError, ValueError):
            pass
    parts.append(f'당일{rate}')
    return '·'.join(parts)


_SELL_ACTION_KR = {'SELL_PROFIT': '익절', 'SELL_STOP_LOSS': '손절', 'SELL_STOP_PROFIT': '익절',
                   'SELL_TRAIL': '트레일', 'SELL_TIME': '타임', 'EOD': '종료청산'}


def _sell_reason(action, ctx: dict) -> str:
    """매도 사유 상세. get_action_in_active 가 반환하는 sell_ctx(kospi1.py `_build_sell`)를
    사람이 읽을 수 있는 한 줄로 요약한다."""
    ctx = ctx or {}
    name = action.name if hasattr(action, 'name') else str(action)
    label = _SELL_ACTION_KR.get(name, name)

    if name == 'SELL_STOP_LOSS':
        if ctx.get('obv_dead_valid') == 'Y':
            return f"{label}(OBV데드크로스, 진입후{ctx.get('bars_held')}봉 유예종료)"
        return f"{label}(가격 -{abs(float(str(ctx.get('profit_pct','0%')).rstrip('%') or 0)):.1f}%, 손절가{ctx.get('stop_price')}↓)"
    if name in ('SELL_PROFIT', 'SELL_STOP_PROFIT'):
        return f"{label}(목표가{ctx.get('target_price')} 도달)"
    if name == 'SELL_TRAIL':
        return (f"{label}({ctx.get('trail_src','atr')}라인, 고점{ctx.get('peak')}→"
                f"{ctx.get('trail_line')}, 고점수익{ctx.get('peak_gain')})")
    if name == 'SELL_TIME':
        over = ctx.get('over_hard') == 'Y'
        return f"{label}({'절대보유한도초과' if over else '추세소진'}, 신고가없음{ctx.get('bars_since_peak')}봉)"
    if name == 'EOD':
        return f"{label}(백테스트 구간 종료, 강제청산)"
    return label


def _name_map(table: str = TABLE_PROD) -> dict:
    """stock_code -> stock_name (해당 테이블에 저장된 이름)."""
    assert table in _ALLOWED_TABLES, f"허용되지 않은 테이블: {table}"
    try:
        rows = session.execute(text(
            f"SELECT DISTINCT stock_code, stock_name FROM {table}")).all()
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


def _simulate(strategy, ui, days: list, reco: dict, names: dict,
              fee_rate: float = FEE_RATE, skip_gapup: bool = SKIP_GAPUP) -> list:
    """매매 루프 순수함수 버전. 출력/그래프/표 없이 trades 리스트만 반환한다.
    run()과 grid-search(옵션 최적화) 양쪽에서 재사용하기 위해 분리했다.
    strategy: 이미 원하는 매도 파라미터가 세팅된 KospiStrategy1 인스턴스.
    ui: UserOptionMeta (포지션 상태 스크래치패드로 재사용됨 — 호출부에서 재사용해도 무방,
        _open_position 이 매번 관련 필드를 덮어쓰기 때문에 콜 간 오염되지 않는다)."""
    trades = []
    mode = 'FLAT'          # FLAT(대기) | PENDING(다음날 시가 체결 대기) | HOLD(보유)
    code = entry_price = entry_date = entry_reason = None
    pend_code = pend_ref = pend_reason = None

    def _open_position(c, row, price, date, reason):
        """포지션 진입: ui 상태 세팅. price=체결가, date=체결일, reason=매수 사유(_buy_reason 결과)."""
        nonlocal code, entry_price, entry_date, entry_reason, mode
        cur = UserCoinInfo.from_dict(row)
        code = c
        entry_price = float(price)
        entry_date = date
        entry_reason = reason
        ui.has_position = True
        ui.avg_price = ui.entry_price = entry_price
        ui.entry_atr = float(cur.atr or 0)
        ui.peak_high = float(cur.high)
        ui.peak_close = float(cur.close)
        ui.bars_since_peak = 0
        ui.bars_held = 0
        mode = 'HOLD'

    def _eval_sell(d, advance: bool):
        """매도판정 1회. advance=True 면 포지션 상태(peak/bars) 선갱신.
        진입일(체결일)은 advance=False — _open_position 에서 이미 초기값 세팅됨(bars_held=0)."""
        nonlocal code, entry_price, entry_date, entry_reason, mode
        rows, by_date = _candles(code)
        if d not in by_date:
            return  # 해당 종목 그날 미거래(휴장/데이터 없음) → 다음날
        idx, cur_row = by_date[d]
        prev_row = rows[idx - 1] if idx > 0 else rows[idx]
        cur = UserCoinInfo.from_dict(cur_row)
        prev = UserCoinInfo.from_dict(prev_row)

        if advance:
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
                'entry_action': 'BUY', 'entry_reason': entry_reason,
                'exit_dt': d, 'exit_price': exit_price,
                'exit_reason': action.name,
                'sell_reason': _sell_reason(action, res.get('sell_ctx')),
                'bars_held': ui.bars_held,
                'ret_gross': gross, 'ret_net': gross - 2 * fee_rate,
            })
            mode = 'FLAT'
            code = entry_price = entry_date = entry_reason = None
            ui.has_position = False

    for di, d in enumerate(days):
        ymd = d.replace('-', '')

        # ── 보유중: 매도판단 (매수/매도 같은 날 동시수행 안 함) ──────────
        if mode == 'HOLD':
            _eval_sell(d, advance=True)
            continue  # 매도했든 아니든 그날은 재매수 안 함

        # ── 다음날 시가 체결 대기 (ENTRY_PRICE='next_open', 1일만 유효) ───
        if mode == 'PENDING':
            rows, by_date = _candles(pend_code)
            if d in by_date:
                idx, row = by_date[d]
                o_px = float(row['open'])
                if skip_gapup and o_px > pend_ref:      # 다음날 시가가 추천일 종가보다↑ → 추격 스킵
                    mode = 'FLAT'                       # 폐기 → 아래 FLAT 스캔(오늘 추천 새로)
                else:
                    _open_position(pend_code, row, o_px, d, pend_reason)  # 다음날 시가 매수
                    _eval_sell(d, advance=False)             # 진입일에도 매도판정
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
            for c, _rate, _action_type in cand:  # 과열 낮은 순, 캔들 있는 첫 종목
                rows, by_date = _candles(c)
                if d in by_date:
                    chosen = (c, by_date[d][1], _rate, _action_type)
                    break
            if not chosen:
                continue
            code_sel, cand_row, cand_rate, cand_action = chosen
            reason = _buy_reason(code_sel, ymd, cand_action, cand_rate)
            if ENTRY_PRICE == 'next_open':
                pend_code = code_sel
                pend_ref = float(cand_row['close'])   # 추천일 종가(갭업 판정 기준)
                pend_reason = reason
                mode = 'PENDING'                      # 다음 거래일 시가에 체결
            else:
                _open_position(code_sel, cand_row, float(cand_row['close']), d, reason)  # 당일 종가 매수
                _eval_sell(d, advance=False)                                     # 진입일에도 매도판정
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
            'entry_action': 'BUY', 'entry_reason': entry_reason,
            'exit_dt': days[-1], 'exit_price': last_close,
            'exit_reason': 'EOD', 'sell_reason': _sell_reason('EOD', None),
            'bars_held': ui.bars_held,
            'ret_gross': gross, 'ret_net': gross - 2 * fee_rate,
        })

    return trades


def run(start: str = START_DATE, end: str = END_DATE,
        init_cash: int = INIT_CASH, fee_rate: float = FEE_RATE,
        table: str = TABLE_PROD, skip_gapup: bool = SKIP_GAPUP) -> dict:
    """table=TABLE_PROD(운영, 기본) 또는 TABLE_TEST(오프라인 테스트 알고리즘).
    skip_gapup=True 면 ENTRY_PRICE='next_open'일 때 다음날 시가가 추천일 종가보다
    위로 갭이면 그 종목은 진입을 포기하고 같은 날 다음 후보를 다시 찾는다."""
    assert table in _ALLOWED_TABLES, f"허용되지 않은 테이블: {table}"
    strategy = KospiStrategy1()
    ui = _user_info()

    days = _trading_days(start, end)
    if not days:
        print(f'거래일 데이터 없음: {start} ~ {end or "최근"} (trade_candle_data 확인)')
        return {}
    reco = _reco_by_day(start, end, table=table)
    names = _name_map(table=table)

    trades = _simulate(strategy, ui, days, reco, names, fee_rate=fee_rate, skip_gapup=skip_gapup)

    label = _TABLE_LABEL[table]
    _report(strategy, start, days, trades, init_cash, label=label, skip_gapup=skip_gapup)
    base_tag = 'gapskip' if (ENTRY_PRICE == 'next_open' and skip_gapup) else 'nogapskip'
    tag = f'{base_tag}_{label}'
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
    summary = KisBacktester(strategy=strategy)._summarize('SIM', trades)
    return {'trades': trades, 'summary': summary, 'table': table, 'label': label}


def compare(start: str = START_DATE, end: str = END_DATE,
            init_cash: int = INIT_CASH, fee_rate: float = FEE_RATE,
            skip_gapup: bool = SKIP_GAPUP) -> dict:
    """운영(trade_buy_target_stock) vs 오프라인 테스트(trade_buy_target_stock_test)를
    동일 기간·동일 매도로직·동일 skip_gapup 설정으로 각각 시뮬레이션하고 나란히 비교한다."""
    print('=' * 70)
    print(f'[1/2] 운영 테이블(trade_buy_target_stock) 시뮬레이션  (갭업매수금지={skip_gapup})')
    print('=' * 70)
    prod = run(start, end, init_cash, fee_rate, table=TABLE_PROD, skip_gapup=skip_gapup)

    print('\n' + '=' * 70)
    print(f'[2/2] 테스트 테이블(trade_buy_target_stock_test — 신규 알고리즘) 시뮬레이션  (갭업매수금지={skip_gapup})')
    print('=' * 70)
    test = run(start, end, init_cash, fee_rate, table=TABLE_TEST, skip_gapup=skip_gapup)

    if not prod or not test:
        print('\n[비교 생략] 한쪽(또는 양쪽) 테이블에 해당 기간 추천/매매가 없습니다.')
        return {'prod': prod, 'test': test}

    _print_comparison(prod, test, init_cash)
    if prod.get('trades') or test.get('trades'):
        try:
            path = _plot_comparison(prod.get('trades', []), test.get('trades', []), init_cash)
            print(f'\n[비교 그래프] {path}')
        except Exception as e:
            print(f'[비교 그래프] 생성 실패: {type(e).__name__}: {e}')

    return {'prod': prod, 'test': test}


def _print_comparison(prod: dict, test: dict, init_cash: int = INIT_CASH) -> None:
    """summary 지표 + 가상자금 최종수익률을 나란히 출력."""
    ps, ts = prod['summary'], test['summary']

    def _final(trades):
        BUY_FEE = SELL_FEE = 0.0011
        cash = init_cash
        for t in trades:
            ep, xp = t['entry_price'], t['exit_price']
            sh = int(cash / (ep * (1 + BUY_FEE))) if ep > 0 else 0
            cash = cash - sh * ep * (1 + BUY_FEE) + sh * xp * (1 - SELL_FEE)
        return round((cash / init_cash - 1) * 100, 2)

    p_final = _final(prod['trades'])
    t_final = _final(test['trades'])

    rows = [
        ('거래건수',              ps['trades'],       ts['trades']),
        ('승률(%)',               ps['win_rate'],      ts['win_rate']),
        ('총수익률(%,복리)',      ps['total_return'],  ts['total_return']),
        ('가상자금 최종수익률(%)', p_final,             t_final),
        ('평균수익(%)',           ps['avg_ret'],       ts['avg_ret']),
        ('평균익절(%)',           ps['avg_win'],       ts['avg_win']),
        ('평균손절(%)',           ps['avg_loss'],      ts['avg_loss']),
        ('Profit Factor',        ps['profit_factor'], ts['profit_factor']),
        ('MDD(%)',                ps['mdd'],           ts['mdd']),
        ('평균보유봉',            ps['avg_bars'],      ts['avg_bars']),
    ]
    print('\n' + '=' * 70)
    print(f"{'지표':<22}{'운영(prod)':>18}{'신규알고리즘(test)':>22}")
    print('-' * 70)
    for name, pv, tv in rows:
        print(f"{name:<22}{str(pv):>18}{str(tv):>22}")
    print('=' * 70)
    print(f"청산사유 — 운영: {ps['exit_breakdown']}")
    print(f"청산사유 — 신규: {ts['exit_breakdown']}")


def _plot_comparison(prod_trades: list, test_trades: list,
                     init_cash: int = INIT_CASH, out_dir: str = PLOT_DIR) -> str:
    """운영 vs 신규 알고리즘 잔액곡선을 한 그래프에 겹쳐서 저장."""
    import os
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    _set_kor_font()

    def _curve(trades):
        BUY_FEE = SELL_FEE = 0.0011
        cash = init_cash
        curve = [init_cash]
        for t in trades:
            ep, xp = t['entry_price'], t['exit_price']
            sh = int(cash / (ep * (1 + BUY_FEE))) if ep > 0 else 0
            cash = cash - sh * ep * (1 + BUY_FEE) + sh * xp * (1 - SELL_FEE)
            curve.append(cash)
        return curve

    p_curve, t_curve = _curve(prod_trades), _curve(test_trades)

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(range(len(p_curve)), p_curve, marker='o', ms=4, color='tab:gray', lw=1.6,
            label=f'운영(prod)  final {(p_curve[-1] / init_cash - 1) * 100:+.1f}%  ({len(prod_trades)}건)')
    ax.plot(range(len(t_curve)), t_curve, marker='o', ms=4, color='tab:blue', lw=1.6,
            label=f'신규알고리즘(test)  final {(t_curve[-1] / init_cash - 1) * 100:+.1f}%  ({len(test_trades)}건)')
    ax.axhline(init_cash, ls='--', color='gray', lw=1)
    ax.set_ylabel('Equity (KRW)')
    ax.set_xlabel('Trade #')
    ax.set_title('buy_target 시뮬 비교: 운영 vs 신규 알고리즘')
    ax.legend(loc='upper left', fontsize=10)
    ax.grid(alpha=0.25)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f'{v / 1e6:.2f}M'))

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, 'sim_compare.png')
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return os.path.abspath(path)


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


def _trunc(s, n=24) -> str:
    s = str(s or '-')
    return s if len(s) <= n else s[:n - 1] + '…'


def _table_image(trades, strategy, init_cash=INIT_CASH, out_dir=PLOT_DIR, tag='') -> str:
    """매매 로그를 '표'로 렌더한 PNG. (코드/종목명/매매일자/가격/매수·매도이유/손익/잔액)"""
    import os
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    _set_kor_font()

    cols = ['#', '코드', '종목명', '매수일', '매수가', '매수이유', '매도일', '매도가',
            '사유', '매도이유', '봉', '손익%', '잔액']
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
            t['entry_dt'], f"{ep:,.0f}", _trunc(t.get('entry_reason'), 26),
            t['exit_dt'], f"{xp:,.0f}",
            _REASON_KR.get(t['exit_reason'], t['exit_reason']),
            _trunc(t.get('sell_reason'), 30),
            str(t['bars_held']), f"{ret:+.2f}", f"{cash:,.0f}",
        ])
        base = '#e8f5e9' if win else '#fdecea'      # 승=연초록 / 패=연빨강
        row_c = [base] * len(cols)
        row_c[11] = '#c8e6c9' if win else '#f5c6cb'  # 손익% 강조
        cell_colors.append(row_c)

    summary = KisBacktester(strategy=strategy)._summarize('SIM', trades)
    final_pct = (cash / init_cash - 1) * 100

    n = len(body)
    fig, ax = plt.subplots(figsize=(19, 1.1 + 0.42 * (n + 1)))
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
    # 종목명/이유 좌측정렬 + 열폭
    widths = [0.025, 0.05, 0.10, 0.06, 0.06, 0.16, 0.06, 0.06, 0.05, 0.19, 0.025, 0.05, 0.08]
    for j, w in enumerate(widths):
        for r in range(n + 1):
            tbl[(r, j)].set_width(w)
    for r in range(1, n + 1):
        tbl[(r, 2)].set_text_props(ha='left')   # 종목명
        tbl[(r, 5)].set_text_props(ha='left')   # 매수이유
        tbl[(r, 9)].set_text_props(ha='left')   # 매도이유

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f'sim_table{("_" + tag) if tag else ""}.png')
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return os.path.abspath(path)


def _report(strategy, start, days, trades, init_cash, label: str = 'prod', skip_gapup: bool = SKIP_GAPUP):
    summary = KisBacktester(strategy=strategy)._summarize('SIM', trades)
    print(f'===== buy_target 실전 시뮬 (KospiStrategy1 매도) — 추천소스: {label} =====')
    print(f'기간: {days[0]} ~ {days[-1]} ({len(days)}거래일) | 1포지션 전량매매')
    print(f'선택: 당일추천만·과열최저(rate↓) | 체결: 매수={ENTRY_PRICE}'
          f'{"(갭업 매수금지)" if (ENTRY_PRICE=="next_open" and skip_gapup) else "(갭업 허용)" if ENTRY_PRICE=="next_open" else ""}, 매도=당일종가')
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
        print(f"{t['entry_dt']} BUY {t['coin']}({t.get('stock_name','')}) @{ep:.0f} x{shares} -> "
              f"{t['exit_dt']} {t['exit_reason']} @{xp:.0f} "
              f"| {t['bars_held']}bars | {t['ret_net'] * 100:+.2f}% → 잔액 {cash:,.0f}원")
        print(f"    매수이유: {t.get('entry_reason', '-')}")
        print(f"    매도이유: {t.get('sell_reason', '-')}")
    print(f'\n[가상자금] 시작 {init_cash:,}원 → 최종 {cash:,.0f}원 '
          f'({cash - init_cash:+,.0f}원 / {(cash / init_cash - 1) * 100:+.2f}%)')


if __name__ == '__main__':
    import argparse

    ap = argparse.ArgumentParser(
        description="trade_buy_target_stock 기반 매매 시뮬레이션 (+ 신규 알고리즘 비교)")
    ap.add_argument('start', nargs='?', default=START_DATE, help='시작일(YYYY-MM-DD)')
    ap.add_argument('end', nargs='?', default=END_DATE, help='종료일(YYYY-MM-DD, 생략 시 최근까지)')
    ap.add_argument('--table', choices=['prod', 'test', 'both'], default='both',
                     help="prod=운영 trade_buy_target_stock만 / test=trade_buy_target_stock_test만 "
                          "/ both=둘 다 시뮬레이션 후 비교(기본값)")
    ap.add_argument('--skip-gapup', action='store_true',
                     help="ENTRY_PRICE='next_open'일 때 다음날 시가가 추천일 종가보다 위로 갭이면 "
                          "그 종목은 매수하지 않는다(기본: 갭업도 추격 매수 허용).")
    args = ap.parse_args()

    if args.table == 'both':
        compare(args.start, args.end, skip_gapup=args.skip_gapup)
    else:
        run(args.start, args.end, table=(TABLE_PROD if args.table == 'prod' else TABLE_TEST),
            skip_gapup=args.skip_gapup)
