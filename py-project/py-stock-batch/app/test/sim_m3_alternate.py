"""
M3 교대매매(시나리오 1) 단일 조합 시뮬레이션 러너.

trade_candle_30m 에 백필된 30분봉으로 KODEX 코스피100(237350) ↔
KODEX 인버스(114800) 교대매매를 재생하고 성과를 출력한다.

사전조건
    TradeCandle30mBackfillJob 으로 두 종목 30분봉이 적재돼 있어야 한다.
    (최소 250봉. 부족하면 지표가 NaN 구간에서 시작해 결과가 왜곡된다)

사용
    poetry run python -m app.test.sim_m3_alternate
    poetry run python -m app.test.sim_m3_alternate --confirm 3 --verbose
    poetry run python -m app.test.sim_m3_alternate --start 2026-06-01 --end 2026-08-13
    poetry run python -m app.test.sim_m3_alternate --macd-mode golden --obv-mode off

optimize_m3_options.py 가 이 모듈의 load_rows()/build_strategy()/run_once() 를
그대로 재사용한다(조합마다 DB 를 다시 읽지 않도록 캐시 포함).
"""
import argparse

from app.batches.services.userService import UserService
from app.config.database import dbConn
from stock_shared.dao.tradeCandle30mDao import TradeCandle30mDao
from stock_shared.dto.userOptionMeta import UserOptionMeta
from stock_shared.strategy.kospi1 import KospiStrategy1
from stock_shared.strategy.m3_alternate import M3AlternateSimulator, ScoreConfig

CODE_A = '237350'   # KODEX 코스피100 (정방향)
CODE_B = '114800'   # KODEX 인버스

_dao = TradeCandle30mDao()
_row_cache: dict = {}      # (code, start, end) → rows. 그리드 서치 재사용용


# ──────────────────────────────────────────────────────────────
def load_rows(session, code: str, start: str = None, end: str = None,
              limit: int = 100000) -> list:
    """30분봉 조회 (오름차순). 동일 조건은 캐시에서 재사용."""
    key = (code, start, end)
    if key in _row_cache:
        return _row_cache[key]

    if start or end:
        rows = _dao.select_by_range(session, code,
                                    start or '1900-01-01 00:00:00',
                                    end or '2999-12-31 23:59:59')
    else:
        rows = _dao.select_latest(session, code, limit=limit)

    # DAO 는 Decimal 을 돌려준다. 전략/시뮬은 float 전제라 여기서 한 번에 변환한다.
    for r in rows:
        for k, v in list(r.items()):
            if k == 'datetime' or v is None:
                continue
            if hasattr(v, 'is_integer') or type(v).__name__ == 'Decimal':
                try:
                    r[k] = float(v)
                except (TypeError, ValueError):
                    pass

    _row_cache[key] = rows
    return rows


def user_info(session) -> UserOptionMeta:
    """운영 user_options 를 그대로 쓴다. 조회 실패 시 최소 기본값."""
    try:
        return UserService().get_user_options(session)
    except Exception:                                   # noqa: BLE001
        ui = UserOptionMeta()
        ui.vol_limit = 0
        ui.vol_surge = 3.0
        ui.delay_date = 5
        ui.macd_recent_day = 20
        ui.bb_over_recent_day = 7
        return ui


def build_strategy(**overrides) -> KospiStrategy1:
    """KospiStrategy1 인스턴스 + 파라미터 오버라이드.

    ⚠ 오타 방지: 존재하지 않는 속성명을 넘기면 조용히 무시되는 대신 에러를 낸다.
       그리드 라벨과 실제 적용 파라미터가 어긋나는 사고를 막는다.
    """
    s = KospiStrategy1()
    for k, v in overrides.items():
        if not hasattr(s, k):
            raise AttributeError(f"KospiStrategy1 에 '{k}' 속성이 없다")
        setattr(s, k, v)
    return s


def run_once(session, *, strategy_kwargs: dict = None, confirm_bars: int = 2,
             fee_rate: float = 0.0015, slippage: float = 0.0,
             score_config: ScoreConfig = None,
             start: str = None, end: str = None, verbose: bool = False) -> dict:
    """단일 조합 시뮬레이션."""
    kw = strategy_kwargs or {}
    sim = M3AlternateSimulator(
        build_strategy(**kw), build_strategy(**kw),
        confirm_bars=confirm_bars, fee_rate=fee_rate,
        slippage=slippage, score_config=score_config,
    )
    rows_a = load_rows(session, CODE_A, start, end)
    rows_b = load_rows(session, CODE_B, start, end)
    return sim.run(CODE_A, CODE_B, rows_a, rows_b, user_info(session), verbose=verbose)


# ──────────────────────────────────────────────────────────────
def print_result(res: dict, show_trades: bool = True):
    print()
    print('=' * 78)
    print(f"M3 교대매매 결과  {res['code_a']} ↔ {res['code_b']}   "
          f"({res['bars']}봉)")
    print('=' * 78)
    if res.get('note'):
        print(f"  note: {res['note']}")

    tr = res['total_return']
    print(f"  교대 횟수      : {res['trades']}회")
    print(f"  총수익률       : {tr:+.2%}")
    print(f"  MDD            : {res['mdd']:.2%}")
    print(f"  Calmar(수익/MDD): {res['calmar']}")
    print(f"  승률           : {res['win_rate']:.1%}")
    print(f"  Profit Factor  : {res['profit_factor']}")
    print(f"  평균 보유봉수  : {res['avg_bars_held']}")
    print('  ─ 벤치마크 ────────────────────────────────────────────')
    print(f"  {res['code_a']} Buy&Hold : {res['bh_a']:+.2%}")
    print(f"  {res['code_b']} Buy&Hold : {res['bh_b']:+.2%}")
    best_bh = max(res['bh_a'], res['bh_b'])
    print(f"  → 전략 - 최선벤치마크 : {tr - best_bh:+.2%}")

    if show_trades and res.get('trade_list'):
        print()
        print('  ─ 거래 내역 ───────────────────────────────────────────')
        print(f"  {'종목':<8} {'진입':<17} {'청산':<17} {'봉':>4} {'수익':>8}  사유")
        for t in res['trade_list']:
            print(f"  {t['coin']:<8} {t['entry_dt']:<17} {t['exit_dt']:<17} "
                  f"{t['bars_held']:>4} {t['ret_net']:>+7.2%}  {t['exit_reason']}")
    print()


# ──────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description='M3 교대매매 시뮬레이션 (시나리오 1)')
    ap.add_argument('--confirm', type=int, default=2,
                    help='매수신호 연속 확인 봉수 (기본 2, 휩쏘 방어)')
    ap.add_argument('--fee', type=float, default=0.0015, help='편도 수수료율')
    ap.add_argument('--slippage', type=float, default=0.0, help='편도 슬리피지율')
    ap.add_argument('--start', help='시작 datetime (YYYY-MM-DD)')
    ap.add_argument('--end', help='종료 datetime (YYYY-MM-DD)')
    ap.add_argument('--macd-mode', choices=['off', 'golden', 'slope'])
    ap.add_argument('--obv-mode', choices=['off', 'golden', 'slope'])
    ap.add_argument('--ma20-mode', choices=['off', 'slope'])
    ap.add_argument('--score-original', action='store_true',
                    help='score 가중치를 매수추천배치 원본(tech.5/fund.3/liq.2)으로')
    ap.add_argument('--verbose', action='store_true', help='신호 발생 시점 출력')
    ap.add_argument('--no-trades', action='store_true', help='거래 내역 생략')
    args = ap.parse_args()

    kw = {}
    if args.macd_mode:
        kw['macd_signal_mode'] = args.macd_mode
    if args.obv_mode:
        kw['obv_signal_mode'] = args.obv_mode
    if args.ma20_mode:
        kw['ma20_signal_mode'] = args.ma20_mode

    sc = ScoreConfig(w_tech=0.5, w_fund=0.3, w_liq=0.2) if args.score_original else None

    session = dbConn.get_session()
    try:
        for code in (CODE_A, CODE_B):
            cnt = _dao.count_by_coin(session, code)
            bounds = _dao.select_bounds(session, code)
            print(f"[데이터] {code}: {cnt}봉 ({bounds['first']} ~ {bounds['last']})")
            if cnt < 250:
                print(f"         ⚠ 250봉 미만 — 지표 워밍업이 부족하다. 백필 확인 필요.")

        res = run_once(session, strategy_kwargs=kw, confirm_bars=args.confirm,
                       fee_rate=args.fee, slippage=args.slippage,
                       score_config=sc, start=args.start, end=args.end,
                       verbose=args.verbose)
        print_result(res, show_trades=not args.no_trades)
    finally:
        session.remove()


if __name__ == '__main__':
    main()
