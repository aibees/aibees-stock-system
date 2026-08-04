from stock_shared.vo.userCoinInfo import UserCoinInfo
from stock_shared.dto.userOptionMeta import UserOptionMeta
from stock_shared.strategy.base import StockStrategy, Action


class KospiStrategy2(StockStrategy):
    """
    HMA + OBV + MACD + 체결강도 조합 전략.

    ── 설계 요지 ──────────────────────────────────────────────────────
    진입(core AND) : HMA 추세전환(상승) AND MACD 신호 AND OBV 신호 를 '동시' 충족.
                     각 신호는 mode(off/golden/slope 또는 off/slope/above)로 개별 튜닝.
    진입(필터)     : 체결강도 >= 임계(기본 100=매수우위) 를 보조 게이트로.
                     추가로 RSI 과매수 차단 / BB 상단추격 금지 / 평균거래량 하한.
                     각 게이트는 enable_* 스위치로 개별 on/off.
    청산(우선순위) : 1.손절(-x% & 20일선 이탈, 또는 OBV 데드크로스)
                    > 2.익절(+y%)
                    > 3.HMA 추세이탈(종가 < HMA)
                    > 4.트레일링(고점 - k*ATR)
                    > 5.타임스탑(보유한도 초과)

    ── 데이터 소스 주의 ──────────────────────────────────────────────
    · HMA          : DB candle 컬럼이 없어 백테스트(KisBacktester)·라이브
                     (compute_indicator_df)에서 종가로 계산해 주입.
    · 체결강도      : 일봉 candle 에 없음. live 는 KIS inquire-ccnl(CTTR/STRN)
                     값을 coin_info.chegyul_strength 로 주입, 백테스트는
                     OHLCV proxy(종가위치*200, 100=중간)로 근사.
    · MACD/OBV      : 기존 DB 지표(macd_g_cross_n / obv_g_cross_n ...) 그대로 사용.
    """

    def __init__(self):
        super().__init__()

        # ── 청산 파라미터 ────────────────────────────────────────────
        self.stop_loss_pct   = 0.05    # -5% 손절(20일선 이탈 동반 시)
        self.take_profit_pct = 0.30    # +30% 익절(전량)
        self.max_hold_bars   = 12      # 보유 봉수 한도(타임스탑 기준)
        self.max_hold_bars_hard = 20   # 절대 보유 한도

        # ── 지표 파라미터 ────────────────────────────────────────────
        self.hma_period       = 20     # HMA 기간(백테스터/라이브가 이 값으로 계산·주입)
        self.rsi_overbought   = 70      # 과매수 진입 차단
        self.vol_ma_mult      = 0.5     # 20일 평균거래량 * 배수 하한(죽은 거래량만 컷)

        # ── 컨펌 층: "거래량 실린 양봉 + 종가 상단 마감" ───────────────
        #  체결강도(외부 API)를 대체하는 백테스트 가능한 당일 매수우위 컨펌.
        #  · 양봉         : close > open
        #  · 거래량 실린  : volume >= 20일 평균거래량 * confirm_vol_mult
        #  · 종가 상단마감 : CLV=(close-low)/(high-low) >= confirm_clv_min
        self.confirm_body_up  = True   # 양봉 요구
        self.confirm_vol_mult = 1.0    # 거래량 >= 평균 * 배수(1.0=평균 이상)
        self.confirm_clv_min  = 0.6    # 종가가 당일 range 상단 60% 이상에서 마감

        # ── 체결강도(외부 API 실값) — 기본 off. 일별 매수/매도체결량 백필 시 켬 ─
        self.chegyul_threshold = 110.0 # 체결강도 하한(100=균형, 110=매수우위)

        # ── 적응형 추세국면 게이트 (S1 이식) ─────────────────────────
        #  최근 regime_window 봉 중 (close<ema60) 비율 = downtrend_ratio.
        #  임계 이상이면 '하락국면' → 떨어지는 칼 방어(상승배열+모멘텀만 통과),
        #  그 외 국면 → 단기선(ema20) 위면 통과(느슨).
        #  ※ downtrend_ratio 는 백테스터/compute_indicator_df 가 주입(별도 계산 불필요).
        self.regime_window          = 90     # 분류기 봉 길이(백테스터가 이 값으로 주입)
        self.regime_threshold       = 0.70   # 이 이상이면 하락국면 → 엄격
        self.regime_strict_need_macd = True  # 하락국면 통과에 macd>=signal 모멘텀 요구

        # ── core 진입 신호 mode ──────────────────────────────────────
        #  hma : 'off'|'slope'(hma 상승 중)|'above'(종가>hma 이면서 hma 상승)
        #        |'inflection'(HMA 상승변곡: 기울기 음→양 전환 당봉)
        #  macd: 'off'|'golden'(골든크로스)|'slope'(기울기 0 이상: macd >= 전봉 macd)
        #  obv : 'off'|'golden'|'slope'(기울기 0 이상)
        #  → MACD/OBV 기본을 slope 로: 골든크로스가 아니어도 기울기만 0 이상이면 통과.
        self.hma_signal_mode  = 'slope'
        self.macd_signal_mode = 'slope'
        self.obv_signal_mode  = 'slope'

        # ── 매수 필터 on/off 스위치 ─────────────────────────────────
        self.enable_hma_filter      = True   # HMA core 신호
        self.enable_macd_filter     = True   # MACD core 신호
        self.enable_obv_filter      = True   # OBV core 신호
        self.enable_confirm_candle  = True   # 컨펌: 거래량 실린 양봉 + 종가 상단마감
        self.enable_chegyul_filter  = False  # 체결강도(외부 실값). 기본 off
        self.enable_rsi_filter      = True   # 과매수 차단
        self.enable_bb_upper_filter = True   # BB 상단 추격 금지
        self.enable_vol_avg_filter  = True   # 평균거래량 하한(죽은 거래량 컷)
        self.enable_regime_gate     = True   # 적응형 추세국면 게이트(하락국면 진입 차단)

        # ── 트레일링(샹들리에) 스탑 ─────────────────────────────────
        self.use_trailing       = True
        self.trail_basis        = 'close'  # 'close'=종가고점 / 'high'=장중고점
        self.trail_activate_pct = 0.08     # 고점수익 +8% 도달해야 ON
        self.k_trail_atr        = 3.0      # 고점 - k*ATR
        self.trail_floor_pct    = 0.10     # ATR 미산출 시 고점 -10%

        # ── 매도 보조 ───────────────────────────────────────────────
        self.obv_dead_min_bars = 5         # OBV 데드크로스 노이즈 무시 봉수
        self.use_hma_exit      = True      # HMA 기반 청산 사용 여부(마스터 on/off)
        #  'break'     = 종가 < HMA 추세이탈 시 청산(기존 동작)
        #  'inflection'= HMA 하락변곡(기울기 양→음 전환) 시 청산
        #  'off'       = HMA 청산 안 함
        self.hma_exit_mode     = 'break'

    # ──────────────────────────────────────────────────────────────
    def configure(self, user_info: UserOptionMeta) -> None:
        """user_options 의 s2_* 값이 있으면 __init__ 기본값을 덮어씁니다."""
        def _f(val, cast=float):
            return cast(val) if val is not None else None

        def _bool(val):
            return bool(int(val)) if val is not None else None

        g = lambda name: getattr(user_info, name, None)

        overrides = {
            'stop_loss_pct':          _f(g('s2_stop_loss_pct')),
            'take_profit_pct':        _f(g('s2_take_profit_pct')),
            'max_hold_bars':          _f(g('s2_max_hold_bars'), int),
            'max_hold_bars_hard':     _f(g('s2_max_hold_bars_hard'), int),
            'hma_period':             _f(g('s2_hma_period'), int),
            'chegyul_threshold':      _f(g('s2_chegyul_threshold')),
            'confirm_body_up':        _bool(g('s2_confirm_body_up')),
            'confirm_vol_mult':       _f(g('s2_confirm_vol_mult')),
            'confirm_clv_min':        _f(g('s2_confirm_clv_min')),
            'rsi_overbought':         _f(g('s2_rsi_overbought'), int),
            'vol_ma_mult':            _f(g('s2_vol_ma_mult')),
            'regime_window':          _f(g('s2_regime_window'), int),
            'regime_threshold':       _f(g('s2_regime_threshold')),
            'regime_strict_need_macd': _bool(g('s2_regime_strict_need_macd')),
            'hma_signal_mode':        g('s2_hma_signal_mode')  or None,
            'macd_signal_mode':       g('s2_macd_signal_mode') or None,
            'obv_signal_mode':        g('s2_obv_signal_mode')  or None,
            'use_trailing':           _bool(g('s2_use_trailing')),
            'trail_activate_pct':     _f(g('s2_trail_activate_pct')),
            'k_trail_atr':            _f(g('s2_k_trail_atr')),
            'trail_floor_pct':        _f(g('s2_trail_floor_pct')),
            'obv_dead_min_bars':      _f(g('s2_obv_dead_min_bars'), int),
            'hma_exit_mode':          g('s2_hma_exit_mode') or None,
            'enable_hma_filter':      _bool(g('s2_enable_hma_filter')),
            'enable_macd_filter':     _bool(g('s2_enable_macd_filter')),
            'enable_obv_filter':      _bool(g('s2_enable_obv_filter')),
            'enable_confirm_candle':  _bool(g('s2_enable_confirm_candle')),
            'enable_chegyul_filter':  _bool(g('s2_enable_chegyul_filter')),
            'enable_regime_gate':     _bool(g('s2_enable_regime_gate')),
            'enable_rsi_filter':      _bool(g('s2_enable_rsi_filter')),
            'enable_bb_upper_filter': _bool(g('s2_enable_bb_upper_filter')),
            'enable_vol_avg_filter':  _bool(g('s2_enable_vol_avg_filter')),
            'use_hma_exit':           _bool(g('s2_use_hma_exit')),
        }
        for attr, val in overrides.items():
            if val is not None:
                setattr(self, attr, val)

    # ──────────────────────────────────────────────────────────────
    def get_action(self, trade_data: list[dict], user_info: UserOptionMeta) -> Action:
        pass

    def get_action_with_prev(self, position_type: str, prev_info: UserCoinInfo,
                             coin_info: UserCoinInfo, user_info: UserOptionMeta):
        self.configure(user_info)

        if position_type == 'watch':
            return self.get_action_in_watch(prev_info, coin_info, user_info)
        if position_type == 'active':
            return self.get_action_in_active(prev_info, coin_info, user_info)
        return None

    # ──────────────────────────────────────────────────────────────
    # 매도 판별 (전량 매도)
    #  1.손절 > 2.익절 > 3.HMA 추세이탈 > 4.트레일링 > 5.타임스탑
    # ──────────────────────────────────────────────────────────────
    def get_action_in_active(self, prev_info: UserCoinInfo, coin_info: UserCoinInfo,
                             user_info: UserOptionMeta) -> dict:
        close = coin_info.close
        entry = user_info.entry_price if user_info.entry_price > 0 else user_info.avg_price

        profit_pct   = (close - entry) / entry if entry > 0 else 0.0
        stop_price   = entry * (1 - self.stop_loss_pct)
        target_price = entry * (1 + self.take_profit_pct)
        is_obv_dead  = coin_info.obv_d_cross_n == 'D'
        is_above_ema20 = close > coin_info.ema20 if coin_info.ema20 else False

        # 손절: OBV 데드크로스는 진입 후 obv_dead_min_bars 이내면 노이즈로 무시
        obv_dead_valid   = is_obv_dead and user_info.bars_held >= self.obv_dead_min_bars
        # 가격 손절: -x% 하회하더라도 20일선 위면 유지
        price_stop_valid = (close <= stop_price) and not is_above_ema20

        # 트레일링 기준선
        peak = (user_info.peak_close if self.trail_basis == 'close' else user_info.peak_high) or close
        atr = float(coin_info.atr) if (coin_info.atr and float(coin_info.atr) > 0) \
              else float(user_info.entry_atr or 0)
        trail_line = peak - self.k_trail_atr * atr if atr > 0 else peak * (1 - self.trail_floor_pct)
        peak_gain   = (peak - entry) / entry if entry > 0 else 0.0
        trail_on    = self.use_trailing and peak_gain >= self.trail_activate_pct
        trail_valid = trail_on and (close <= trail_line)

        # HMA 청산: mode 별. 진입 초기 노이즈 방지 위해 obv_dead_min_bars 이후에만.
        hma = float(coin_info.hma or 0)
        cur_hslope  = float(coin_info.hma_slope or 0)
        prev_hslope = float(prev_info.hma_slope or 0)
        _exit_mode = self.hma_exit_mode if self.use_hma_exit else 'off'
        _min_bars  = user_info.bars_held >= self.obv_dead_min_bars
        if _exit_mode == 'inflection':
            # HMA 하락변곡: 직전봉 기울기 >=0, 당봉 기울기 <0 (고점 전환)
            hma_exit_valid = hma > 0 and prev_hslope >= 0 and cur_hslope < 0 and _min_bars
            hma_exit_reason = 'HMA_PEAK'
        elif _exit_mode == 'break':
            hma_exit_valid = hma > 0 and (close < hma) and _min_bars
            hma_exit_reason = 'HMA_BREAK'
        else:
            hma_exit_valid = False
            hma_exit_reason = ''

        # 1. 손절
        if price_stop_valid or obv_dead_valid:
            return self._build_sell(coin_info, user_info, Action.SELL_STOP_LOSS, profit_pct,
                                    stop_price, target_price,
                                    extra={'obv_dead': 'Y' if is_obv_dead else 'N',
                                           'obv_dead_valid': 'Y' if obv_dead_valid else 'N',
                                           'is_above_ema20': 'Y' if is_above_ema20 else 'N'})
        # 2. 익절
        if close >= target_price:
            return self._build_sell(coin_info, user_info, Action.SELL_PROFIT, profit_pct,
                                    stop_price, target_price)
        # 3. HMA 청산 (추세이탈 or 하락변곡)
        if hma_exit_valid:
            return self._build_sell(coin_info, user_info, Action.SELL_TRAIL, profit_pct,
                                    stop_price, target_price,
                                    extra={'reason': hma_exit_reason, 'hma': round(hma, 2)})
        # 4. 트레일링
        if trail_valid:
            return self._build_sell(coin_info, user_info, Action.SELL_TRAIL, profit_pct,
                                    stop_price, target_price,
                                    extra={'peak': round(peak, 2), 'trail_line': round(trail_line, 2),
                                           'peak_gain': str(round(peak_gain * 100, 2)) + '%',
                                           'trail_basis': self.trail_basis})
        # 5. 타임스탑
        if user_info.bars_held >= self.max_hold_bars:
            over_hard = user_info.bars_held >= self.max_hold_bars_hard
            # 추세 생존(수익+20일선 위+HMA 위)이면 보류, 아니면 타임스탑
            trend_alive = (profit_pct > 0) and is_above_ema20 and (hma <= 0 or close >= hma)
            if trend_alive and not over_hard:
                return self._build_sell(coin_info, user_info, Action.HOLD, profit_pct,
                                        stop_price, target_price, extra={'time_stop': 'EXTENDED'})
            return self._build_sell(coin_info, user_info, Action.SELL_TIME, profit_pct,
                                    stop_price, target_price,
                                    extra={'over_hard': 'Y' if over_hard else 'N'})

        return self._build_sell(coin_info, user_info, Action.HOLD, profit_pct,
                                stop_price, target_price)

    def _build_sell(self, coin_info: UserCoinInfo, user_info: UserOptionMeta, action: Action,
                    profit_pct: float, stop_price: float, target_price: float,
                    extra: dict = None) -> dict:
        sell_ctx = {
            'profit_pct':   str(round(profit_pct * 100, 2)) + "%",
            'entry_price':  user_info.entry_price,
            'bars_held':    user_info.bars_held,
            'stop_price':   round(stop_price, 2),
            'target_price': round(target_price, 2),
        }
        if extra:
            sell_ctx.update(extra)
        return {
            'stock_code':    coin_info.coin_code,
            'stock_name':    '',
            'action_type':   action.name,
            'result_action': action,
            'todayStock': {
                'open':   coin_info.open,
                'high':   coin_info.high,
                'low':    coin_info.low,
                'close':  coin_info.close,
                'volume': coin_info.volume,
            },
            'sell_ctx': sell_ctx,
        }

    # ──────────────────────────────────────────────────────────────
    # 매수 판별 : HMA + MACD + OBV core AND + 체결강도 필터
    # ──────────────────────────────────────────────────────────────
    def get_action_in_watch(self, prev_info: UserCoinInfo, coin_info: UserCoinInfo,
                            user_info: UserOptionMeta) -> dict:
        rate_str = str(round((coin_info.close - prev_info.close) / prev_info.close * 100, 2)) + "%" \
            if prev_info.close > 0 else "0%"

        # ── core 신호 원자료 ────────────────────────────────────────
        hma      = float(coin_info.hma or 0)
        prev_hma = float(prev_info.hma or 0)
        hma_slope_up = hma > 0 and prev_hma > 0 and hma > prev_hma
        close_above_hma = hma > 0 and coin_info.close > hma
        # HMA 상승변곡: 직전봉 기울기 <=0, 당봉 기울기 >0 (저점 전환)
        cur_hslope  = float(coin_info.hma_slope or 0)
        prev_hslope = float(prev_info.hma_slope or 0)
        hma_infl_up = hma > 0 and prev_hma > 0 and prev_hslope <= 0 and cur_hslope > 0

        is_macd_g     = coin_info.macd_g_cross_n == 'G'
        is_obv_g      = coin_info.obv_g_cross_n  == 'G'
        # slope 모드: 기울기 0 이상(보합 포함)이면 OK. 골든크로스 불필요.
        macd_slope_up = float(coin_info.macd) >= float(prev_info.macd)
        obv_slope_up  = float(coin_info.obv)  >= float(prev_info.obv)

        def _hma_ok(mode):
            if mode == 'off':        return True
            if mode == 'above':      return close_above_hma and hma_slope_up
            if mode == 'inflection': return hma_infl_up
            return hma_slope_up  # 'slope'(기본)

        def _sig_ok(mode, is_golden, is_slope_up):
            if mode == 'slope': return is_slope_up
            if mode == 'off':   return True
            return is_golden    # 'golden'

        hma_sig  = _hma_ok(self.hma_signal_mode)
        macd_sig = _sig_ok(self.macd_signal_mode, is_macd_g, macd_slope_up)
        obv_sig  = _sig_ok(self.obv_signal_mode,  is_obv_g,  obv_slope_up)

        # enable_* 가 꺼진 core 는 통과(True)로 취급
        hma_core  = (not self.enable_hma_filter)  or hma_sig
        macd_core = (not self.enable_macd_filter) or macd_sig
        obv_core  = (not self.enable_obv_filter)  or obv_sig
        core_all  = hma_core and macd_core and obv_core

        # freshness: 직전 봉에도 동일 core 를 통과했으면 신규 아님(재진입 억제).
        #  golden mode 는 직전 크로스 flag 로, slope/above/off 는 판정 불가/무조건 → 억제 안 함(False).
        def _prev_sig_ok(mode, prev_is_golden):
            if mode == 'golden': return prev_is_golden
            if mode == 'off':    return True
            return False  # slope/above: 직전 기울기 불가지 → 억제 안 함
        prev_hma_core  = (not self.enable_hma_filter)  or _prev_sig_ok(self.hma_signal_mode, False)
        prev_macd_core = (not self.enable_macd_filter) or _prev_sig_ok(self.macd_signal_mode, prev_info.macd_g_cross_n == 'G')
        prev_obv_core  = (not self.enable_obv_filter)  or _prev_sig_ok(self.obv_signal_mode,  prev_info.obv_g_cross_n  == 'G')
        prev_core_all  = prev_hma_core and prev_macd_core and prev_obv_core
        is_fresh = core_all and not prev_core_all

        # ── 컨펌 층: 거래량 실린 양봉 + 종가 상단 마감 ─────────────────
        rng = float(coin_info.high) - float(coin_info.low)
        clv = ((float(coin_info.close) - float(coin_info.low)) / rng) if rng > 0 else 0.5
        is_body_up      = coin_info.close > coin_info.open              # 양봉
        is_vol_loaded   = (coin_info.vol_avg <= 0) or \
                          (coin_info.volume >= coin_info.vol_avg * self.confirm_vol_mult)
        is_close_strong = clv >= self.confirm_clv_min                  # 종가 상단 마감
        confirm_candle_ok = ((not self.confirm_body_up) or is_body_up) \
                            and is_vol_loaded and is_close_strong

        # ── 체결강도(외부 실값) — 기본 off, 백필 시 사용 ──────────────
        chegyul = float(coin_info.chegyul_strength or 0)
        is_chegyul_ok     = chegyul >= self.chegyul_threshold

        # ── 보조 필터 ───────────────────────────────────────────────
        is_rsi_overbought = coin_info.rsi >= self.rsi_overbought
        is_under_bb_upper = coin_info.close <= coin_info.bb_upper
        is_vol_above_avg  = (coin_info.vol_avg <= 0) or \
                            (coin_info.volume >= coin_info.vol_avg * self.vol_ma_mult)
        is_vol_surge      = coin_info.vol_surge_n > 0

        # ── 적응형 추세국면 게이트 (S1 이식) ─────────────────────────
        dt_ratio = float(coin_info.downtrend_ratio or 0.0)
        is_downtrend_regime = dt_ratio >= self.regime_threshold
        above_ema20  = bool(coin_info.ema20 and coin_info.close > coin_info.ema20)
        above_ema60  = bool(coin_info.ema60 and coin_info.close > coin_info.ema60)
        ema_stack_up = bool(coin_info.ema20 and coin_info.ema60 and coin_info.ema20 > coin_info.ema60)
        macd_ge_sig  = float(coin_info.macd) >= float(coin_info.macd_s)
        if is_downtrend_regime:
            # 하락국면 → 방어: 완전 상승배열(+모멘텀)만 통과. 떨어지는 칼 차단.
            regime_gate  = above_ema60 and ema_stack_up and \
                           (macd_ge_sig or not self.regime_strict_need_macd)
            regime_label = 'DOWN'
        else:
            # 상승/중립국면 → 단기선 위면 통과(느슨)
            regime_gate  = above_ema20
            regime_label = 'UP'

        def _build_result(action: Action, extra: dict = None) -> dict:
            indicator = {
                'hma':               round(hma, 2),
                'hma_slope':         round(hma - prev_hma, 4),
                'hma_slope_up':      'Y' if hma_slope_up else 'N',
                'close_above_hma':   'Y' if close_above_hma else 'N',
                'hma_sig':           'Y' if hma_sig  else 'N',
                'macd_cross':        coin_info.macd_g_cross_n,
                'macd_sig':          'Y' if macd_sig else 'N',
                'obv_cross':         coin_info.obv_g_cross_n,
                'obv_sig':           'Y' if obv_sig  else 'N',
                'core_all':          'Y' if core_all else 'N',
                'is_fresh':          'Y' if is_fresh else 'N',
                'clv':               round(clv, 3),
                'is_body_up':        'Y' if is_body_up      else 'N',
                'is_vol_loaded':     'Y' if is_vol_loaded   else 'N',
                'is_close_strong':   'Y' if is_close_strong else 'N',
                'confirm_candle_ok': 'Y' if confirm_candle_ok else 'N',
                'chegyul_strength':  round(chegyul, 2),
                'is_chegyul_ok':     'Y' if is_chegyul_ok    else 'N',
                'is_rsi_overbought': 'Y' if is_rsi_overbought else 'N',
                'is_under_bb_upper': 'Y' if is_under_bb_upper else 'N',
                'is_vol_above_avg':  'Y' if is_vol_above_avg  else 'N',
                'is_vol_surge':      'Y' if is_vol_surge      else 'N',
                'regime':            regime_label,
                'downtrend_ratio':   round(dt_ratio, 2),
                'regime_gate':       'Y' if regime_gate       else 'N',
                'rsi':               round(coin_info.rsi, 2),
                'macd':              round(float(coin_info.macd), 4),
                'hma_mode':          self.hma_signal_mode,
                'macd_mode':         self.macd_signal_mode,
                'obv_mode':          self.obv_signal_mode,
            }
            if extra:
                indicator.update(extra)
            return {
                'stock_code': coin_info.coin_code,
                'stock_name': '',
                'action_type': action.name,
                'todayStock': {
                    'open': coin_info.open, 'high': coin_info.high, 'low': coin_info.low,
                    'close': coin_info.close, 'volume': coin_info.volume, 'rate': rate_str,
                },
                'indicator': indicator,
            }

        # ── [core] HMA+MACD+OBV 동시(신선) ─────────────────────────
        if not is_fresh:
            return _build_result(Action.HOLD)

        # ── [컨펌] 거래량 실린 양봉 + 종가 상단 마감 ──────────────────
        if self.enable_confirm_candle and not confirm_candle_ok:
            return _build_result(Action.HOLD)
        # ── [필터] 개별 on/off ─────────────────────────────────────
        if self.enable_chegyul_filter and not is_chegyul_ok:
            return _build_result(Action.HOLD)
        if self.enable_rsi_filter and is_rsi_overbought:
            return _build_result(Action.HOLD)
        if self.enable_bb_upper_filter and not is_under_bb_upper:
            return _build_result(Action.HOLD)
        if self.enable_vol_avg_filter and not is_vol_above_avg:
            return _build_result(Action.HOLD)
        # ── [추세국면 게이트] 하락국면=상승배열+모멘텀만, 그 외=단기선 위 ─────
        if self.enable_regime_gate and not regime_gate:
            return _build_result(Action.HOLD)

        # ── [진입] 거래량 급증 동반 시 BUY_SURGE ──────────────────
        result_action = Action.BUY_SURGE if is_vol_surge else Action.BUY
        return _build_result(result_action)
