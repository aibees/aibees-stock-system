"""
m3_alternate.py — M3 정·역 ETF 교대매매 시뮬레이터 (테스트 시나리오 1).

시나리오 1 정의
    대상 2종목. KODEX 코스피100(237350) / KODEX 인버스(114800). 30분봉.

    1) 시작: 두 종목을 동시에 매수체크. **둘 다 매수신호가 확정된 경우**
       score 가 높은 쪽에 진입한다. 한쪽만 신호면 그쪽.
    2) 보유 중: 상대 종목의 매수신호만 감시한다.
       상대 신호가 확정되면 → 보유분 전량 매도 + 상대 종목 매수 (교대).
    3) 상대 신호가 뜨기 전까지는 무조건 보유. 손절/익절 없음.
       → 항상 둘 중 하나를 100% 들고 있다(현금 대기 없음).

    휩쏘 방어: 매수신호가 confirm_bars 회 **연속** 나와야 '확정'으로 본다.
               기본 2. 1로 두면 확인 없이 즉시 실행(구 동작).

매수신호 판정
    KospiStrategy1.get_action_in_watch 를 그대로 쓴다.
    30분봉이라 봉 길이만 다를 뿐 지표 파이프라인(compute_indicator_df)은 동일하다.
    최적화 대상 파라미터도 KospiStrategy1 의 필드를 그대로 쓴다.

score
    매수추천배치(StockBuyCheckJob → StockService.assign_ranks)와 동일한 계산.
    stock_shared.strategy.scoring 으로 추출해 양쪽이 같은 함수를 쓴다.

    ⚠ M3 에서의 주의점 2가지:
      · fund(재무 30%): ETF 는 eps/per/pbr 이 없어 **양쪽 다 0점**. 상대비교에
        기여하지 않으므로 기본 가중치에서 제외한다(w_fund=0).
      · liq(유동성 20%): 후보가 2개뿐이라 min-max 정규화하면 항상 한쪽 1.0 /
        한쪽 0.0 이 된다. 거래대금이 큰 정방향 ETF 가 상시 +20점을 먹어
        사실상 "코스피100 우선" 편향이 된다 → 기본 w_liq=0.
      → 기본값은 tech 100%. 원본 가중치를 그대로 쓰고 싶으면
        ScoreConfig(w_tech=.5, w_fund=.3, w_liq=.2) 로 명시하면 된다.

체결 가정
    봉 종가로 신호를 판정하고 **다음 봉 시가**로 체결한다(KisBacktester 와 동일).
    매도·매수가 같은 시점에 일어나므로 교대 1회당 수수료가 2번 나간다
    (매도 1 + 매수 1). fee_rate 는 편도 기준.
"""
from dataclasses import dataclass, field

from stock_shared.dto.userOptionMeta import UserOptionMeta
from stock_shared.strategy import scoring
from stock_shared.strategy.backtester import KisBacktester
from stock_shared.vo.userCoinInfo import UserCoinInfo

__all__ = ["ScoreConfig", "M3AlternateSimulator"]

# Action enum 의 매수 계열은 전부 'BUY' 로 시작한다
# (BUY / BUY_BREAKOUT / BUY_DIP / BUY_ALL / BUY_SURGE).
# 새 매수 액션이 추가돼도 자동으로 잡히도록 prefix 로 판정한다.


@dataclass
class ScoreConfig:
    """score 가중치. 기본값은 M3(ETF 2종목) 에 맞춘 tech 100%.

    원본 매수추천배치와 동일하게 쓰려면 (0.5, 0.3, 0.2).
    """
    w_tech: float = 1.0
    w_fund: float = 0.0
    w_liq: float = 0.0
    # tech 하위 가중치. None 이면 scoring.TECH_WEIGHTS(운영 기본값).
    tech_weights: dict = field(default=None)


class M3AlternateSimulator:
    """시나리오 1 교대매매 시뮬레이터.

    strategy 는 종목마다 **별도 인스턴스**를 받는다. 두 종목이 같은 파라미터를
    쓰더라도 인스턴스를 공유하면 내부 상태(configure 결과)가 섞일 수 있다.
    """

    def __init__(self, strategy_a, strategy_b, *,
                 confirm_bars: int = 2,
                 fee_rate: float = 0.0015,
                 score_config: ScoreConfig = None,
                 slippage: float = 0.0):
        self.strategy_a = strategy_a
        self.strategy_b = strategy_b
        self.confirm_bars = max(1, int(confirm_bars))
        self.fee_rate = fee_rate
        self.slippage = slippage
        self.sc = score_config or ScoreConfig()

    # ------------------------------------------------------------------
    # 전처리
    # ------------------------------------------------------------------
    @staticmethod
    def align(rows_a: list, rows_b: list) -> tuple:
        """두 종목 봉을 datetime 교집합으로 맞춘다.

        한쪽에만 있는 봉(거래정지·데이터 누락)을 그대로 두면 인덱스가 밀려
        서로 다른 시각을 비교하게 된다. 교집합만 남기는 게 안전하다.
        """
        map_a = {str(r['datetime']): r for r in rows_a}
        map_b = {str(r['datetime']): r for r in rows_b}
        common = sorted(set(map_a) & set(map_b))
        return [map_a[k] for k in common], [map_b[k] for k in common]

    def _prepare(self, rows_a: list, rows_b: list) -> tuple:
        """정렬 + 파생컬럼 주입. KisBacktester.enrich_rows 를 재사용한다."""
        a, b = self.align(rows_a, rows_b)
        KisBacktester(strategy=self.strategy_a).enrich_rows(a)
        KisBacktester(strategy=self.strategy_b).enrich_rows(b)
        return a, b

    # ------------------------------------------------------------------
    # 신호 / 스코어
    # ------------------------------------------------------------------
    def _eval(self, strategy, prev_row: dict, row: dict, ui: UserOptionMeta) -> tuple:
        """(매수신호 여부, score) 반환.

        get_action_in_watch 는 HOLD 를 돌려줄 때도 indicator dict 를 채워 주므로
        신호가 없어도 score 는 계산된다 → '둘 다 신호 없음' 상황에서도 비교 가능.
        """
        prev_info = UserCoinInfo.from_dict(prev_row)
        coin_info = UserCoinInfo.from_dict(row)
        res = strategy.get_action_with_prev('watch', prev_info, coin_info, ui)

        if isinstance(res, dict):
            action_name = res.get('action_type', 'HOLD')
            ind = res.get('indicator', {}) or {}
            today = res.get('todayStock', {}) or {}
        else:                                   # Action enum 이 바로 온 경우
            action_name = getattr(res, 'name', str(res))
            ind, today = {}, {}

        is_buy = action_name.startswith('BUY')

        tech = scoring.tech_score(ind, weights=self.sc.tech_weights)
        fund = scoring.fund_score({}) if self.sc.w_fund else 0.0
        turnover = float(today.get('close') or row.get('close') or 0) * \
                   float(today.get('volume') or row.get('volume') or 0)
        return is_buy, tech, fund, turnover

    def _score_of(self, tech: float, fund: float, liq: float) -> float:
        return scoring.total_score(tech, fund, liq,
                                   w_tech=self.sc.w_tech,
                                   w_fund=self.sc.w_fund,
                                   w_liq=self.sc.w_liq)

    # ------------------------------------------------------------------
    # 본체
    # ------------------------------------------------------------------
    def run(self, code_a: str, code_b: str, rows_a: list, rows_b: list,
            base_user_info: UserOptionMeta, verbose: bool = False) -> dict:
        a, b = self._prepare(rows_a, rows_b)
        if len(a) < 3:
            return self._summarize(code_a, code_b, [], a, b, note='봉 부족')

        ui_a = self._clone_ui(base_user_info)
        ui_b = self._clone_ui(base_user_info)

        streak = {'A': 0, 'B': 0}          # 연속 매수신호 카운트
        holding = None                     # None | 'A' | 'B'
        entry_price = 0.0
        entry_dt = ''
        entry_bar = 0
        pending = None                     # 다음 봉 시가에 진입할 쪽

        trades = []

        for i in range(1, len(a)):
            row_a, row_b = a[i], b[i]

            # ── 전봉에서 확정된 교대를 이번 봉 시가로 체결 ──────────────
            if pending is not None:
                tgt_row = row_a if pending == 'A' else row_b
                px = self._fill_price(tgt_row, side='buy')

                if holding is not None:     # 기존 보유 청산
                    cur_row = row_a if holding == 'A' else row_b
                    exit_px = self._fill_price(cur_row, side='sell')
                    trades.append(self._close_trade(
                        holding, code_a, code_b, entry_dt, entry_price,
                        str(cur_row['datetime']), exit_px, i - entry_bar))

                holding = pending
                entry_price = px
                entry_dt = str(tgt_row['datetime'])
                entry_bar = i
                pending = None

            # ── 이번 봉 종가 기준 신호 판정 ────────────────────────────
            buy_a, tech_a, fund_a, turn_a = self._eval(self.strategy_a, a[i - 1], row_a, ui_a)
            buy_b, tech_b, fund_b, turn_b = self._eval(self.strategy_b, b[i - 1], row_b, ui_b)

            streak['A'] = streak['A'] + 1 if buy_a else 0
            streak['B'] = streak['B'] + 1 if buy_b else 0

            confirmed_a = streak['A'] >= self.confirm_bars
            confirmed_b = streak['B'] >= self.confirm_bars

            if i + 1 >= len(a):
                continue                    # 다음 봉이 없으면 체결 불가

            if holding is None:
                # ── 최초 진입: 확정된 쪽 중 score 높은 쪽 ──────────────
                cands = []
                if confirmed_a:
                    cands.append('A')
                if confirmed_b:
                    cands.append('B')
                if not cands:
                    continue

                if len(cands) == 1:
                    pick = cands[0]
                else:
                    liq_a, liq_b = scoring.normalize_liquidity([turn_a, turn_b])
                    sa = self._score_of(tech_a, fund_a, liq_a)
                    sb = self._score_of(tech_b, fund_b, liq_b)
                    pick = 'A' if sa >= sb else 'B'
                    if verbose:
                        print(f"  [{row_a['datetime']}] 동시확정 → "
                              f"A({code_a}) {sa:.2f} vs B({code_b}) {sb:.2f} → {pick}")

                pending = pick
                streak['A'] = streak['B'] = 0     # 진입 후 카운트 초기화

            else:
                # ── 보유 중: 상대 신호만 본다 ────────────────────────
                other = 'B' if holding == 'A' else 'A'
                if (confirmed_b if other == 'B' else confirmed_a):
                    pending = other
                    streak['A'] = streak['B'] = 0
                    if verbose:
                        oc = code_b if other == 'B' else code_a
                        print(f"  [{row_a['datetime']}] 교대 신호 → {oc} "
                              f"({self.confirm_bars}봉 연속)")

        # ── 종료 시점 미청산 → 마지막 종가로 정리 ──────────────────────
        if holding is not None:
            last = a[-1] if holding == 'A' else b[-1]
            trades.append(self._close_trade(
                holding, code_a, code_b, entry_dt, entry_price,
                str(last['datetime']), float(last['close']),
                len(a) - 1 - entry_bar, reason='EOD'))

        return self._summarize(code_a, code_b, trades, a, b)

    # ------------------------------------------------------------------
    # 헬퍼
    # ------------------------------------------------------------------
    def _fill_price(self, row: dict, side: str) -> float:
        """체결가 = 해당 봉 시가 (없으면 종가) ± 슬리피지."""
        px = float(row.get('open') or row.get('close') or 0)
        if self.slippage:
            px *= (1 + self.slippage) if side == 'buy' else (1 - self.slippage)
        return px

    def _close_trade(self, side: str, code_a: str, code_b: str,
                     entry_dt: str, entry_px: float,
                     exit_dt: str, exit_px: float, bars: int,
                     reason: str = 'FLIP') -> dict:
        code = code_a if side == 'A' else code_b
        gross = (exit_px - entry_px) / entry_px if entry_px > 0 else 0.0
        net = gross - 2 * self.fee_rate          # 매수 1 + 매도 1
        return {
            'side': side, 'coin': code,
            'entry_dt': entry_dt, 'entry_price': entry_px,
            'exit_dt': exit_dt, 'exit_price': exit_px,
            'bars_held': bars, 'exit_reason': reason,
            'ret_gross': gross, 'ret_net': net,
        }

    @staticmethod
    def _clone_ui(base: UserOptionMeta) -> UserOptionMeta:
        ui = UserOptionMeta()
        for k, v in vars(base).items():
            setattr(ui, k, v)
        ui.has_position = False
        return ui

    # ------------------------------------------------------------------
    def _summarize(self, code_a: str, code_b: str, trades: list,
                   rows_a: list, rows_b: list, note: str = '') -> dict:
        n = len(trades)
        if n == 0:
            return {
                'code_a': code_a, 'code_b': code_b, 'trades': 0,
                'total_return': 0.0, 'mdd': 0.0, 'calmar': 0.0,
                'win_rate': 0.0, 'profit_factor': 0.0,
                'avg_bars_held': 0.0, 'bars': len(rows_a),
                'bh_a': self._buy_hold(rows_a), 'bh_b': self._buy_hold(rows_b),
                'trade_list': [], 'note': note or '거래 없음',
            }

        # 복리 자본곡선. 교대마다 전액 재투자.
        equity = [1.0]
        for t in trades:
            equity.append(equity[-1] * (1 + t['ret_net']))

        peak = equity[0]
        mdd = 0.0
        for e in equity:
            peak = max(peak, e)
            if peak > 0:
                mdd = max(mdd, (peak - e) / peak)

        wins = [t['ret_net'] for t in trades if t['ret_net'] > 0]
        losses = [t['ret_net'] for t in trades if t['ret_net'] <= 0]
        gain = sum(wins)
        loss = abs(sum(losses))
        pf = (gain / loss) if loss > 0 else ('inf' if gain > 0 else 0.0)

        total_return = equity[-1] - 1.0
        calmar = (total_return / mdd) if mdd > 0 else ('inf' if total_return > 0 else 0.0)

        return {
            'code_a': code_a, 'code_b': code_b,
            'trades': n,
            'total_return': round(total_return, 4),
            'mdd': round(mdd, 4),
            'calmar': calmar if isinstance(calmar, str) else round(calmar, 3),
            'win_rate': round(len(wins) / n, 4),
            'profit_factor': pf if isinstance(pf, str) else round(pf, 3),
            'avg_bars_held': round(sum(t['bars_held'] for t in trades) / n, 1),
            'bars': len(rows_a),
            'bh_a': self._buy_hold(rows_a),
            'bh_b': self._buy_hold(rows_b),
            'equity': [round(e, 5) for e in equity],
            'trade_list': trades,
            'note': note,
        }

    @staticmethod
    def _buy_hold(rows: list) -> float:
        """벤치마크: 첫 봉 시가 매수 → 마지막 봉 종가 청산."""
        if len(rows) < 2:
            return 0.0
        first = float(rows[0].get('open') or rows[0].get('close') or 0)
        last = float(rows[-1].get('close') or 0)
        return round((last - first) / first, 4) if first > 0 else 0.0
