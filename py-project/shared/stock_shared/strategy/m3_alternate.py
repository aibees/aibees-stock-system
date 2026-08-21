"""
m3_alternate.py — M3 정·역 ETF 교대매매 시뮬레이터 (테스트 시나리오 1).

시나리오 1 정의
    대상 2종목. KODEX 코스피100(237350) / KODEX 인버스(114800). 30분봉.

    1) 진입: 두 종목을 동시에 체크해 **먼저 매수신호가 확정되는 쪽**에 들어간다.
       같은 봉에 둘 다 확정되면 score 가 높은 쪽.
    2) 보유 중 청산 트리거 (우선순위 순)
         ① 가격 라인 — 손절 / 익절 / 트레일링          → 장중 터치 즉시
         ② 모멘텀 이탈(REVERSE) — 전략이 SELL 판정      → 다음 봉 시가
         ③ 상대 종목 매수신호 확정(FLIP)               → 다음 봉 시가, 갈아타기
    3) 청산 후에는 **반대편을 바로 사지 않는다.** 현금으로 빠진 뒤
       두 종목 중 먼저 신호를 띄우는 쪽으로 재진입한다(1)과 같은 경로).
       → 노출도가 100% 미만이 될 수 있다.

    휩쏘 방어: 매수신호가 confirm_bars 회 **연속** 나와야 '확정'으로 본다.
               이탈 판정은 연속 확인 없이 1봉 — 진입은 신중, 이탈은 빠르게.

매수/이탈 신호 판정
    strategy.get_action_with_prev(position_type, prev, cur, ui) 하나로 위임한다.
      position_type='watch'  → 매수 신호 (BUY* 면 확정 카운트 +1)
      position_type='active' → 이탈 신호 (SELL* 면 REVERSE 청산)
    판정식은 전략 클래스가 정한다. 시뮬레이터는 상태 전이만 담당한다.

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
                 slippage: float = 0.0,
                 stop_loss_pct: float = None,
                 take_profit_pct: float = None,
                 trail_drawdown_pct: float = None,
                 trail_activate_pct: float = 0.0,
                 exit_on_reverse: bool = True,
                 flip_on_signal: bool = True):
        """
        청산 라인 (KospiStrategy1 과 동일 개념. None 이면 미사용)
            stop_loss_pct      : 진입가 대비 -x% 손절.        예) 0.02 = -2%
            take_profit_pct    : 진입가 대비 +x% 익절.        예) 0.05 = +5%
            trail_drawdown_pct : 보유 중 고점 대비 -x% 트레일링.
            trail_activate_pct : 고점수익이 이 값을 넘어야 트레일링 ON.
                                 진입 직후 휩쏘로 바로 털리는 걸 막는다.

        exit_on_reverse : 보유 종목 모멘텀 이탈 시 즉시 청산 (기본 True)
            보유 중인 종목의 모멘텀이 꺾이면 상대 신호를 기다리지 않고
            곧바로 청산한다(반대편을 바로 사지는 않는다). 사유 코드 'REVERSE'.
            진입은 confirm_bars 연속 확인으로 신중하게, 이탈은 1봉으로 빠르게 —
            이 비대칭이 의도다. 손실을 오래 끌고 가는 게 최대 리스크라서.
            판정식은 전략 클래스가 get_action_with_prev('active', ...) 로 정한다.

        ── 청산 후에는 항상 현금 대기 ────────────────────────────────
            REVERSE · STOP · TRAIL · TP 어느 사유든 **반대편을 바로 사지 않는다**.
            현금으로 빠진 뒤, 두 종목 중 **먼저 매수신호(confirm_bars 연속)를
            띄우는 쪽**으로 다시 들어간다. 같은 봉에 둘 다 확정되면 score 로 가른다.

            왜 즉시 교대를 안 하나:
              내 종목이 꺾였다는 게 곧 상대가 오른다는 뜻은 아니다.
              정·역 ETF 라도 둘 다 방향을 못 잡고 진동하는 구간이 있고,
              그때 무조건 넘어가면 양쪽에서 번갈아 맞으며 수수료만 태운다.
              진입 근거는 항상 '그 종목의 매수신호' 하나로 통일한다.

            청산 시 streak 를 0으로 리셋하므로, 직전까지 쌓여 있던 신호로
            즉시 재진입하지 않는다(= 자연스러운 쿨다운).
            직전에 청산한 종목도 다시 후보에 포함된다 — 새로 confirm_bars 를
            채웠다면 그건 유효한 신규 신호다.

        flip_on_signal : 보유 중 상대 종목 신호가 뜨면 갈아탈지 (기본 True)
            False 면 보유 중에는 상대를 아예 보지 않는다. 청산은 오직
            REVERSE / 가격 라인으로만 일어나고, 그 뒤 현금에서 재진입한다.

        체결 가정
            라인 청산은 **장중 터치 즉시** 체결로 본다(저가/고가가 라인을
            뚫으면 라인 가격). 30분봉 안에서 실제로 닿았다면 라이브에서도
            체결됐을 것이기 때문. 단 시가가 이미 라인을 넘겨 갭이 났으면
            시가로 체결한다(라인 가격에 못 받는다).

            REVERSE 는 봉 종가 판정이므로 청산도 다음 봉 시가.
        """
        self.strategy_a = strategy_a
        self.strategy_b = strategy_b
        self.confirm_bars = max(1, int(confirm_bars))
        self.fee_rate = fee_rate
        self.slippage = slippage
        self.sc = score_config or ScoreConfig()
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.trail_drawdown_pct = trail_drawdown_pct
        self.trail_activate_pct = trail_activate_pct or 0.0
        self.exit_on_reverse = exit_on_reverse
        self.flip_on_signal = flip_on_signal

    @staticmethod
    def _reverse_signal(strategy, prev_row: dict, row: dict, ui) -> bool:
        """보유 종목의 모멘텀 이탈 여부.

        strategy 에 get_action_with_prev('active', ...) 를 물어 SELL 계열이면 True.
        판정 기준 자체는 전략이 정한다
        (SimpleSignalStrategy 는 MACD↓ AND OBV↓ AND RSI↓).
        """
        res = strategy.get_action_with_prev(
            'active', UserCoinInfo.from_dict(prev_row),
            UserCoinInfo.from_dict(row), ui)
        name = res.get('action_type', 'HOLD') if isinstance(res, dict) \
            else getattr(res, 'name', 'HOLD')
        return name.startswith('SELL')

    @property
    def has_exit_lines(self) -> bool:
        return any((self.stop_loss_pct, self.take_profit_pct,
                    self.trail_drawdown_pct))

    def _check_exit(self, row: dict, entry: float, peak: float) -> tuple:
        """이번 봉에서 청산 라인에 닿았는지 판정.

        반환: (사유, 체결가) 또는 (None, None)
        여러 라인이 동시에 닿으면 **손절 우선**(보수적).
        """
        if entry <= 0:
            return None, None
        o = float(row.get('open') or row.get('close') or 0)
        hi = float(row.get('high') or o)
        lo = float(row.get('low') or o)

        # ── 손절 ──────────────────────────────────────────────────
        if self.stop_loss_pct:
            line = entry * (1 - self.stop_loss_pct)
            if lo <= line:
                # 갭하락으로 시가가 이미 라인 아래면 라인 가격에 못 받는다
                return 'STOP', min(line, o)

        # ── 트레일링 (고점 대비 되돌림) ─────────────────────────────
        if self.trail_drawdown_pct and peak > 0:
            gain = (peak - entry) / entry
            if gain >= self.trail_activate_pct:
                line = peak * (1 - self.trail_drawdown_pct)
                if lo <= line:
                    return 'TRAIL', min(line, o)

        # ── 익절 ──────────────────────────────────────────────────
        if self.take_profit_pct:
            line = entry * (1 + self.take_profit_pct)
            if hi >= line:
                return 'TP', max(line, o)

        return None, None

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
        holding = None                     # None | 'A' | 'B'  (None = 현금)
        entry_price = 0.0
        entry_dt = ''
        entry_bar = 0
        peak_high = 0.0                    # 보유 중 최고가 (트레일링 기준)
        pending = None                     # 'A'|'B'(매수) | 'CASH'(청산만) | None
        pending_reason = 'FLIP'            # 청산 사유 라벨

        trades = []

        for i in range(1, len(a)):
            row_a, row_b = a[i], b[i]

            # ── 전봉에서 확정된 매수/청산을 이번 봉 시가로 체결 ──────────
            #   pending = 'A' | 'B' (해당 종목 매수) | 'CASH' (청산만)
            if pending is not None:
                if holding is not None:     # 기존 보유 청산
                    cur_row = row_a if holding == 'A' else row_b
                    exit_px = self._fill_price(cur_row, side='sell')
                    trades.append(self._close_trade(
                        holding, code_a, code_b, entry_dt, entry_price,
                        str(cur_row['datetime']), exit_px, i - entry_bar,
                        reason=pending_reason))

                if pending == 'CASH':
                    holding = None
                    entry_price = 0.0
                    peak_high = 0.0
                else:
                    tgt_row = row_a if pending == 'A' else row_b
                    px = self._fill_price(tgt_row, side='buy')
                    holding = pending
                    entry_price = px
                    entry_dt = str(tgt_row['datetime'])
                    entry_bar = i
                    peak_high = float(tgt_row.get('high') or px)

                pending = None
                pending_reason = 'FLIP'

            # ── 청산 라인 판정 (신호보다 먼저) ──────────────────────────
            # 리스크 관리가 진입 판단보다 우선한다. 같은 봉에서 손절선을 뚫고
            # 상대 신호도 떴다면 손절이 먼저 나가고, 재진입은 다음 확정을 기다린다.
            if holding is not None and self.has_exit_lines:
                cur_row = row_a if holding == 'A' else row_b
                peak_high = max(peak_high, float(cur_row.get('high') or 0))
                reason, exit_px = self._check_exit(cur_row, entry_price, peak_high)
                if reason:
                    trades.append(self._close_trade(
                        holding, code_a, code_b, entry_dt, entry_price,
                        str(cur_row['datetime']), exit_px, i - entry_bar,
                        reason=reason))

                    # 가격 라인 청산은 **현금 대기**다.
                    # 라인은 리스크 컷이지 방향 판단이 아니다. 지표가 아직
                    # 이탈을 말하지 않았는데 반대편으로 넘어가면 근거 없이
                    # 포지션을 뒤집는 셈이다. 방향 전환은 REVERSE 가 담당한다.
                    if verbose:
                        pnl = (exit_px - entry_price) / entry_price
                        hc = code_a if holding == 'A' else code_b
                        print(f"  [{cur_row['datetime']}] {reason} → {hc} "
                              f"청산 {exit_px:,.0f} ({pnl:+.2%}) · 현금 대기")

                    holding = None
                    entry_price = 0.0
                    peak_high = 0.0
                    # 청산 직후 남아있던 신호로 즉시 재진입하지 않도록 리셋.
                    # 다시 confirm_bars 를 채워야 한다 = 자연스러운 쿨다운.
                    streak['A'] = streak['B'] = 0

            # ── 이번 봉 종가 기준 신호 판정 ────────────────────────────
            buy_a, tech_a, fund_a, turn_a = self._eval(self.strategy_a, a[i - 1], row_a, ui_a)
            buy_b, tech_b, fund_b, turn_b = self._eval(self.strategy_b, b[i - 1], row_b, ui_b)

            streak['A'] = streak['A'] + 1 if buy_a else 0
            streak['B'] = streak['B'] + 1 if buy_b else 0

            confirmed_a = streak['A'] >= self.confirm_bars
            confirmed_b = streak['B'] >= self.confirm_bars

            if i + 1 >= len(a):
                continue                    # 다음 봉이 없으면 체결 불가

            # ── 보유 종목 모멘텀 이탈 → 즉시 청산(현금) ────────────────
            # 상대 신호를 기다리지 않고 나온다.
            # 진입은 신중하게(연속 확인), 이탈은 빠르게 — 비대칭이 의도다.
            # 손실을 오래 끌고 가는 게 이 전략의 최대 리스크라서.
            # 단 나온 뒤에는 반대편을 바로 사지 않고 신호를 기다린다.
            if holding is not None and self.exit_on_reverse:
                st = self.strategy_a if holding == 'A' else self.strategy_b
                prev_r = a[i - 1] if holding == 'A' else b[i - 1]
                cur_r = row_a if holding == 'A' else row_b
                if self._reverse_signal(st, prev_r, cur_r,
                                        ui_a if holding == 'A' else ui_b):
                    # 반대편을 바로 사지 않는다. 다음 봉 시가에 **청산만** 하고
                    # 현금에서 두 종목 중 먼저 신호 뜨는 쪽을 기다린다.
                    pending = 'CASH'
                    pending_reason = 'REVERSE'
                    streak['A'] = streak['B'] = 0
                    if verbose:
                        hc = code_a if holding == 'A' else code_b
                        print(f"  [{cur_r['datetime']}] REVERSE → {hc} "
                              f"모멘텀 이탈 → 청산 후 현금 대기")
                    continue                # 아래 매수 판정 건너뜀

            if holding is None:
                # ── 진입: 먼저 확정된 쪽. 동시면 score 높은 쪽 ──────────
                # 최초 시작과 모든 청산 후(REVERSE/STOP/TRAIL/TP)가 이 경로를
                # 공유한다. 즉 '둘 중 먼저 매수신호 오는 쪽으로 재진입'.
                # 직전에 청산한 종목도 후보에 포함된다 — 청산 시 streak 를
                # 0으로 리셋했으므로 새로 confirm_bars 를 채웠다면 유효한 신규
                # 신호이고, 굳이 배제할 근거가 없다.
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

            elif self.flip_on_signal:
                # ── 보유 중: 상대 신호로 갈아타기 ─────────────────────
                # 이건 '청산 후 대기' 가 아니라 상대의 **매수신호**에 따른
                # 직접 교대다. 진입 근거가 신호라는 점에서 재진입과 동일하다.
                # flip_on_signal=False 면 이 경로가 꺼지고, 청산은 오직
                # REVERSE / 가격 라인으로만 일어난다.
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
                'by_reason': {}, 'exposure': 0.0,
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

        # 청산사유별 집계 — 손절이 몇 번 나갔고 거기서 얼마를 잃었는지
        by_reason = {}
        for t in trades:
            r = t['exit_reason']
            agg = by_reason.setdefault(r, {'n': 0, 'sum': 0.0})
            agg['n'] += 1
            agg['sum'] += t['ret_net']
        for agg in by_reason.values():
            agg['sum'] = round(agg['sum'], 4)

        # 시장 노출도 — 손절이 생기면 현금 대기 구간이 발생한다
        held = sum(t['bars_held'] for t in trades)
        exposure = min(held / max(len(rows_a) - 1, 1), 1.0)

        return {
            'code_a': code_a, 'code_b': code_b,
            'trades': n,
            'by_reason': by_reason,
            'exposure': round(exposure, 4),
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
