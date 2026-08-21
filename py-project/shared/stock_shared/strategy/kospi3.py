"""
kospi3.py — M3 (KODEX 코스피100 / KODEX 인버스 **독립 운용**) 전략.

운용모드 M3
    두 ETF 를 교대(둘 중 하나만 보유)로 굴리지 않는다.
    **각 종목이 자기 신호로만 진입/청산**하고, 신호가 없으면 현금으로 쉰다.
    둘 다 신호가 있으면 둘 다 들 수 있고, 둘 다 없으면 전액 현금이다.

    교대 방식을 버린 이유: 정·역 ETF 라도 둘 다 방향을 못 잡고 진동하는
    구간이 있다. 그때 무조건 반대편으로 넘어가면 양쪽에서 번갈아 맞으며
    수수료만 태운다. 진입 근거를 항상 '그 종목의 매수신호' 하나로 통일한다.

진입 (4개 전부 AND, confirm_bars 봉 **연속**)
    1) MACD  기울기 상승   macd  > 직전봉
    2) OBV   기울기 상승   obv   > 직전봉
    3) MA20  기울기 상승   ema20 > 직전봉   ※ 컬럼명은 ema20 이나 실제는 20봉 SMA
    4) RSI < rsi_overbought (기본 70)       ※ 수준 판정(과매수 차단)

청산 (우선순위 순)
    ① 가격 라인 — 손절 / 익절 / 트레일링       (장중 터치 즉시)
    ② 모멘텀 이탈(SELL_TREND) — 아래 3개 AND, **연속 확인 없이 1봉**
         MACD 기울기 하락 · OBV 기울기 하락 · RSI 기울기 하락
         ※ RSI 는 진입에선 수준, 청산에선 기울기를 본다.
            70 아래여도 계속 내려가면 이탈이다.
         ※ MA20 은 청산 판정에서 제외. 후행성이 커서 이미 꺾인 뒤에야
            기울기가 음수로 돌아 청산이 늦어진다.
    청산 후에는 현금 대기. 새로 confirm_bars 를 채워야 재진입한다.

타임프레임
    30분봉 전제다(trade_candle_30m). 임계값이 30분봉 스케일로 맞춰져 있다.
      · stop_loss_pct 기본 0.02 — KospiStrategy1 의 0.05 는 일봉 기준이라
        30분봉에서는 거의 안 걸린다(실측 30분봉 ATR/종가 ≈ 0.82%).
      · confirm_bars 3 = 1시간 30분.
    일봉에 그대로 쓰면 손절이 과하게 타이트해진다.

호출 규약
    · 진입 판정은 **여러 봉**이 필요하다(confirm_bars 연속).
      → get_result_with_action(trade_data, user_info) 를 쓴다. 상태를 들지 않고
        매번 최근 봉들에서 연속 횟수를 다시 센다(재시작·다중 프로세스 안전).
    · get_action_in_watch(prev, coin, ...) 는 **1봉 조건만** 본다(연속 미적용).
      confirm_bars > 1 이면 이 메서드만으로 매수 판정을 내리면 안 된다.
    · 청산은 1봉으로 충분하므로 get_action_in_active(prev, coin, ...) 그대로 쓴다.
      worker 의 SellStrategy.evaluate 가 이 경로를 탄다.
"""
from stock_shared.dto.userOptionMeta import UserOptionMeta
from stock_shared.strategy.base import Action, StockStrategy
from stock_shared.vo.userCoinInfo import UserCoinInfo


def _f(v, default=0.0) -> float:
    """Decimal / None / '' / 문자열 → float."""
    if v is None or v == '':
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _b(v, default: bool) -> bool:
    """0/1, '0'/'1', 'Y'/'N', True/False → bool. None 이면 default."""
    if v is None or v == '':
        return default
    if isinstance(v, str):
        s = v.strip().upper()
        if s in ('Y', 'TRUE', '1'):
            return True
        if s in ('N', 'FALSE', '0'):
            return False
        return default
    try:
        return bool(int(v))
    except (TypeError, ValueError):
        return bool(v)


class KospiStrategy3(StockStrategy):
    """M3 : ETF 2종목 독립 운용."""

    MODE_CODE = 'M3'

    def __init__(self):
        super().__init__()
        # ── 대상 종목 (참고용. 실제 대상은 worker 가 정한다) ──────────
        self.long_code = '237350'    # KODEX 코스피100
        self.short_code = '114800'   # KODEX 인버스

        # ── 진입 ──────────────────────────────────────────────────
        self.confirm_bars = 3        # 4조건 연속 충족 봉수. 1 이면 확인 없이 즉시
        self.rsi_overbought = 70     # 이 값 이상이면 진입 차단
        self.enable_macd_up = True   # 조건별 on/off (튜닝·검증용)
        self.enable_obv_up = True
        self.enable_ma20_up = True
        self.enable_rsi_filter = True

        # ── 청산: 모멘텀 이탈 ──────────────────────────────────────
        self.exit_on_reverse = True
        self.exit_macd_down = True
        self.exit_obv_down = True
        self.exit_rsi_down = True

        # ── 청산: 가격 라인 (None/0 이면 미사용) ────────────────────
        self.stop_loss_pct = 0.02        # -2% 손절
        self.take_profit_pct = None      # 익절 미사용
        self.use_trailing = False
        self.trail_drawdown_pct = None   # 고점 대비 -x%
        self.trail_activate_pct = 0.0    # 고점수익 이 값 초과 시 트레일링 ON

    # ══════════════════════════════════════════════════════════════
    # 유저 설정 주입
    # ══════════════════════════════════════════════════════════════
    def configure(self, user_info: UserOptionMeta) -> None:
        """user_option_m3(s3_*) 값을 인스턴스에 반영. None 이면 기본값 유지."""
        g = lambda k: getattr(user_info, k, None)          # noqa: E731

        def _set_f(attr, key, allow_zero_as_none=True):
            v = g(key)
            if v is None or v == '':
                return
            fv = _f(v, None if allow_zero_as_none else 0.0)
            if fv is None:
                return
            setattr(self, attr, (fv or None) if allow_zero_as_none else fv)

        def _set_i(attr, key):
            v = g(key)
            if v not in (None, ''):
                try:
                    setattr(self, attr, int(v))
                except (TypeError, ValueError):
                    pass

        def _set_b(attr, key):
            v = g(key)
            if v not in (None, ''):
                setattr(self, attr, _b(v, getattr(self, attr)))

        def _set_s(attr, key):
            v = g(key)
            if v not in (None, ''):
                setattr(self, attr, str(v))

        _set_s('long_code', 's3_long_code')
        _set_s('short_code', 's3_short_code')

        _set_i('confirm_bars', 's3_confirm_bars')
        _set_i('rsi_overbought', 's3_rsi_overbought')
        _set_b('enable_macd_up', 's3_enable_macd_up')
        _set_b('enable_obv_up', 's3_enable_obv_up')
        _set_b('enable_ma20_up', 's3_enable_ma20_up')
        _set_b('enable_rsi_filter', 's3_enable_rsi_filter')

        _set_b('exit_on_reverse', 's3_exit_on_reverse')
        _set_b('exit_macd_down', 's3_exit_macd_down')
        _set_b('exit_obv_down', 's3_exit_obv_down')
        _set_b('exit_rsi_down', 's3_exit_rsi_down')

        _set_f('stop_loss_pct', 's3_stop_loss_pct')
        _set_f('take_profit_pct', 's3_take_profit_pct')
        _set_b('use_trailing', 's3_use_trailing')
        _set_f('trail_drawdown_pct', 's3_trail_drawdown_pct')
        # 활성 임계는 0 이 '즉시 활성' 이라는 의미를 가지므로 0 을 None 으로 죽이지 않는다
        _set_f('trail_activate_pct', 's3_trail_activate_pct', allow_zero_as_none=False)

        # confirm_bars 는 1 미만이 될 수 없다
        self.confirm_bars = max(1, int(self.confirm_bars or 1))

    # ══════════════════════════════════════════════════════════════
    # 1봉 조건 판정 (진입/청산 공통 빌딩블록)
    # ══════════════════════════════════════════════════════════════
    def buy_conditions(self, prev_info: UserCoinInfo, coin_info: UserCoinInfo) -> dict:
        """진입 4조건의 개별 판정. 값 자체도 같이 돌려준다(로그·디버깅용)."""
        macd_up = _f(coin_info.macd) > _f(prev_info.macd)
        obv_up = _f(coin_info.obv) > _f(prev_info.obv)
        ma20_up = _f(coin_info.ema20) > _f(prev_info.ema20)
        rsi = _f(coin_info.rsi)
        rsi_ok = rsi < self.rsi_overbought
        return {
            'macd_up': macd_up, 'obv_up': obv_up,
            'ma20_up': ma20_up, 'rsi_ok': rsi_ok, 'rsi': rsi,
            'macd_delta': _f(coin_info.macd) - _f(prev_info.macd),
            'obv_delta': _f(coin_info.obv) - _f(prev_info.obv),
            'ma20_delta': _f(coin_info.ema20) - _f(prev_info.ema20),
        }

    def is_buy_bar(self, prev_info: UserCoinInfo, coin_info: UserCoinInfo) -> bool:
        """이 봉 하나가 진입 조건을 만족하는가(연속 확인은 별도)."""
        c = self.buy_conditions(prev_info, coin_info)
        return ((c['macd_up'] or not self.enable_macd_up)
                and (c['obv_up'] or not self.enable_obv_up)
                and (c['ma20_up'] or not self.enable_ma20_up)
                and (c['rsi_ok'] or not self.enable_rsi_filter))

    def exit_conditions(self, prev_info: UserCoinInfo, coin_info: UserCoinInfo) -> dict:
        macd_down = _f(coin_info.macd) < _f(prev_info.macd)
        obv_down = _f(coin_info.obv) < _f(prev_info.obv)
        rsi_down = _f(coin_info.rsi) < _f(prev_info.rsi)
        return {'macd_down': macd_down, 'obv_down': obv_down, 'rsi_down': rsi_down}

    def is_reverse_bar(self, prev_info: UserCoinInfo, coin_info: UserCoinInfo) -> bool:
        """모멘텀 이탈 여부. 활성화된 조건이 하나도 없으면 False(오작동 방지)."""
        if not self.exit_on_reverse:
            return False
        c = self.exit_conditions(prev_info, coin_info)
        used = []
        if self.exit_macd_down:
            used.append(c['macd_down'])
        if self.exit_obv_down:
            used.append(c['obv_down'])
        if self.exit_rsi_down:
            used.append(c['rsi_down'])
        return bool(used) and all(used)

    # ══════════════════════════════════════════════════════════════
    # 연속 카운트 — 상태를 들지 않는다
    # ══════════════════════════════════════════════════════════════
    def buy_streak(self, trade_data: list) -> int:
        """trade_data 끝에서부터 진입조건 연속 충족 봉수.

        인스턴스에 카운터를 두지 않는 이유:
          worker 재시작·다중 프로세스·종목 2개 동시 운용에서 카운터가
          오염된다. 매번 최근 봉들에서 다시 세면 항상 같은 결론이 나온다.

        trade_data 는 datetime 오름차순 dict 리스트(마지막이 최신 확정봉).
        """
        n = len(trade_data)
        if n < 2:
            return 0
        streak = 0
        # 최대 confirm_bars 까지만 보면 판정에 충분하다
        for i in range(n - 1, 0, -1):
            prev = UserCoinInfo.from_dict(trade_data[i - 1])
            cur = UserCoinInfo.from_dict(trade_data[i])
            if self.is_buy_bar(prev, cur):
                streak += 1
                if streak >= self.confirm_bars:
                    break
            else:
                break
        return streak

    # ══════════════════════════════════════════════════════════════
    # 판정 진입점
    # ══════════════════════════════════════════════════════════════
    def get_result_with_action(self, trade_data: list, user_info: UserOptionMeta) -> dict:
        """미보유 종목의 매수 판정. **연속 확인이 적용되는 유일한 경로.**

        trade_data: datetime 오름차순 봉 리스트. 최소 confirm_bars + 1 개 필요.
        """
        if not trade_data or len(trade_data) < 2:
            return self._build_watch(None, None, Action.HOLD, {},
                                     streak=0, note='봉 부족')

        prev_info = UserCoinInfo.from_dict(trade_data[-2])
        coin_info = UserCoinInfo.from_dict(trade_data[-1])
        conds = self.buy_conditions(prev_info, coin_info)

        need = self.confirm_bars
        if len(trade_data) < need + 1:
            return self._build_watch(prev_info, coin_info, Action.HOLD, conds,
                                     streak=0,
                                     note=f'이력 부족({len(trade_data)}봉 < {need + 1})')

        streak = self.buy_streak(trade_data)
        action = Action.BUY if streak >= need else Action.HOLD
        return self._build_watch(prev_info, coin_info, action, conds, streak=streak)

    def get_action(self, trade_data: list, user_info: UserOptionMeta) -> Action:
        """Action 만 필요할 때. 내부적으로 get_result_with_action 을 탄다."""
        return self.get_result_with_action(trade_data, user_info).get(
            'result_action', Action.HOLD)

    def get_action_with_prev(self, position_type: str, prev_info: UserCoinInfo,
                             coin_info: UserCoinInfo, user_info: UserOptionMeta) -> dict:
        if position_type == 'active':
            return self.get_action_in_active(prev_info, coin_info, user_info)
        return self.get_action_in_watch(prev_info, coin_info, user_info)

    # ── 미보유 (1봉 조건만) ────────────────────────────────────────
    def get_action_in_watch(self, prev_info: UserCoinInfo, coin_info: UserCoinInfo,
                            user_info: UserOptionMeta) -> dict:
        """이 봉 하나가 진입조건을 만족하는지만 본다.

        ⚠ confirm_bars > 1 일 때 **이 결과만으로 매수하면 안 된다.**
          연속 확인이 빠져 휩쏘에 그대로 노출된다.
          실매매 판정은 get_result_with_action(trade_data, ...) 를 써야 한다.
          (백테스터처럼 2봉만 넘기는 호출부와의 호환을 위해 남겨둔 메서드)
        """
        conds = self.buy_conditions(prev_info, coin_info)
        ok = self.is_buy_bar(prev_info, coin_info)
        return self._build_watch(prev_info, coin_info,
                                 Action.BUY if ok else Action.HOLD, conds,
                                 streak=1 if ok else 0,
                                 note=None if self.confirm_bars == 1
                                 else f'1봉 판정(confirm_bars={self.confirm_bars} 미적용)')

    # ── 보유 (청산 판정) ──────────────────────────────────────────
    def get_action_in_active(self, prev_info: UserCoinInfo, coin_info: UserCoinInfo,
                             user_info: UserOptionMeta) -> dict:
        close = _f(coin_info.close)
        entry = _f(user_info.entry_price) or _f(user_info.avg_price)
        profit_pct = (close - entry) / entry if entry > 0 else 0.0

        stop_price = entry * (1 - self.stop_loss_pct) if (entry and self.stop_loss_pct) else 0.0
        target_price = entry * (1 + self.take_profit_pct) if (entry and self.take_profit_pct) else 0.0

        # 트레일링 — 고점 대비 되돌림. peak_high 는 worker 가 실시간 갱신해 넘긴다.
        peak = _f(user_info.peak_high) or close
        peak_gain = (peak - entry) / entry if entry > 0 else 0.0
        trail_line = 0.0
        trail_on = False
        if self.use_trailing and self.trail_drawdown_pct and peak > 0:
            trail_on = peak_gain >= self.trail_activate_pct
            trail_line = peak * (1 - self.trail_drawdown_pct)

        ex = self.exit_conditions(prev_info, coin_info)
        reverse = self.is_reverse_bar(prev_info, coin_info)

        # ── 우선순위: 손절 > 트레일링 > 익절 > 모멘텀 이탈 ──────────
        # 리스크 컷이 먼저다. 같은 봉에 손절선과 이탈이 함께 걸리면
        # 손절로 기록해야 사후 분석에서 원인이 흐려지지 않는다.
        if stop_price and close <= stop_price:
            action, reason = Action.SELL_STOP_LOSS, '손절선 이탈'
        elif trail_on and trail_line and close <= trail_line:
            action, reason = Action.SELL_TRAIL, '트레일링 스탑'
        elif target_price and close >= target_price:
            action, reason = Action.SELL_PROFIT, '익절선 도달'
        elif reverse:
            action, reason = Action.SELL_TREND, '모멘텀 이탈(MACD↓·OBV↓·RSI↓)'
        else:
            action, reason = Action.HOLD, None

        indicator = {
            'macd_down': 'Y' if ex['macd_down'] else 'N',
            'obv_down': 'Y' if ex['obv_down'] else 'N',
            'rsi_down': 'Y' if ex['rsi_down'] else 'N',
            'is_reverse': 'Y' if reverse else 'N',
            'rsi': round(_f(coin_info.rsi), 2),
            'peak_gain': round(peak_gain, 4),
            'trail_on': 'Y' if trail_on else 'N',
        }
        sell_ctx = {
            'profit_pct': str(round(profit_pct * 100, 2)) + '%',
            'entry_price': entry,
            'bars_held': getattr(user_info, 'bars_held', 0),
            'stop_price': round(stop_price, 2),
            'target_price': round(target_price, 2),
            'trail_line': round(trail_line, 2) if trail_line else None,
            'sell_reason': reason,
        }
        return {
            'stock_code': coin_info.coin_code,
            'stock_name': '',
            'action_type': action.name,
            'result_action': action,
            'todayStock': self._today(coin_info),
            'indicator': indicator,
            'sell_ctx': sell_ctx,
        }

    # ══════════════════════════════════════════════════════════════
    # 결과 빌더
    # ══════════════════════════════════════════════════════════════
    @staticmethod
    def _today(coin_info) -> dict:
        if coin_info is None:
            return {}
        return {
            'open': coin_info.open, 'high': coin_info.high,
            'low': coin_info.low, 'close': coin_info.close,
            'volume': coin_info.volume,
        }

    def _build_watch(self, prev_info, coin_info, action: Action, conds: dict,
                     streak: int = 0, note: str = None) -> dict:
        indicator = {
            'macd_up': 'Y' if conds.get('macd_up') else 'N',
            'obv_up': 'Y' if conds.get('obv_up') else 'N',
            'ma20_up': 'Y' if conds.get('ma20_up') else 'N',
            'rsi_ok': 'Y' if conds.get('rsi_ok') else 'N',
            'rsi': round(conds.get('rsi', 0.0), 2),
            'macd_delta': round(conds.get('macd_delta', 0.0), 4),
            'obv_delta': round(conds.get('obv_delta', 0.0), 2),
            'ma20_delta': round(conds.get('ma20_delta', 0.0), 4),
            'streak': streak,
            'confirm_bars': self.confirm_bars,
        }
        if note:
            indicator['note'] = note
        return {
            'stock_code': coin_info.coin_code if coin_info is not None else '',
            'stock_name': '',
            'action_type': action.name,
            'result_action': action,
            'todayStock': self._today(coin_info),
            'indicator': indicator,
        }
