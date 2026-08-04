from stock_shared.vo.userCoinInfo import UserCoinInfo
from app.domain.dto.userOptionMeta import UserOptionMeta
from app.ext_services.StockStrategy import StockStrategy, Action


class KospiStrategy1(StockStrategy):
    def __init__(self):
        super().__init__()
        # ── 005070 백테스트 결론 반영 ─────────────────────────────
        # 진입 엣지: MACD + OBV '동시' 골든크로스 (단독 신호는 동전던지기)
        # 청산 우선순위: 1.손절(-5% or OBV 데드크로스) > 2.익절(+30%)
        #             > 3.트레일링(고점-k*ATR) > 4.동적 타임스탑(12봉)
        self.stop_loss_pct = 0.05      # -5% 손절
        self.take_profit_pct = 0.30    # +30% 익절 (전량)
        self.max_hold_bars = 12         # 12봉 보유 한도(동적 타임스탑 기준)
        self.rsi_overbought = 70       # 과매수 진입 차단 기준
        self.vol_ma_window = 20        # 평균 거래량 산정 기간
        # 진입 최소 거래량 = 20일 평균 * 배수.
        # 005070 검증상 엣지 신호가 '평균 이하' 거래량에서 나와, 1.0(평균 이상)은
        # 신호를 거의 다 죽임 → 죽은 거래량만 거르는 하한선(0.5)으로 설정.
        self.vol_ma_mult = 0.5

        # ── 066430(상승)·048910(하락) 비교분석 결론: 적응형 추세국면 게이트 ──
        # 기존 단일 is_uptrend(ema20>ema60)는 종목 성격을 구분 못해,
        #   · 상승종목(066430): 급등 초입(ema 약세배열)까지 차단 → 최대 수익 +63% 거래 누락
        #   · 하락종목(048910): 약한 반등에도 통과 → 떨어지는 칼 매수
        # 해결: 최근 N봉 close<ema60 비율(downtrend_ratio)로 국면을 먼저 분류한 뒤
        #   게이트 강도를 바꾼다. 격자탐색 최적값 = 윈도우 90봉 / 임계값 0.70.
        #   (066430 max ratio 0.62 → 항상 느슨, 048910 60% 구간 → 엄격 라우팅)
        self.regime_window = 90          # 분류기 봉 길이 (백테스터/라이브가 ratio 주입)
        self.regime_threshold = 0.70     # 이 이상이면 하락국면 → 엄격 게이트
        self.strict_need_macd_up = True  # 엄격: macd >= signal 모멘텀 확인 요구
        self.loose_need_vol_surge = True # 느슨: 거래량 급증 동반 진입만 허용(급등 초입 포착)
        self.surge_relax_mult = 2.0      # 상승국면 느슨 게이트의 완화 급증 배수(전봉 대비). 3배 vol_surge_n 보완
        # 하락국면 거래량-급증 우회: 하락국면이라도 '전봉 대비 N배' 거래량 급증 + 단기선 위면
        #   엄격 배열요건(ema20>ema60)을 면제하고 진입 허용 → 급반등 초입 포착(예: 109070 03-11)
        self.downtrend_surge_bypass = True
        self.surge_bypass_mult = 2.0     # 급증 판정 배수 (전봉 거래량 대비). 2.0 = 2배

        # ── #1 트레일링(샹들리에) 스탑 ───────────────────────────────────────
        # 고점 - k*ATR 아래로 종가가 내려오면 전량 청산. 진입 직후·초기 변동성
        # (특히 윗꼬리)에서의 휩쏘를 막기 위해 '고점 기준 수익 +activate%' 도달
        # 이후에만 활성화. trail_basis='close'는 종가 고점을 기준으로 삼아
        # 장중 꼬리(예: 128660 04/06 장중 3900 후 종가 3510)에 둔감하다.
        self.use_trailing       = True
        self.trail_basis        = 'close'  # 'close'=종가 고점 / 'high'=장중 고점
        self.trail_activate_pct = 0.08     # 고점수익 +8% 도달해야 트레일링 ON
        self.k_trail_atr        = 3.0      # 고점 - k*ATR (작을수록 타이트=빨리 매도). 종목 튜닝 포인트
        self.trail_floor_pct    = 0.10     # ATR 미산출 시 대체: 고점 대비 -10%

        # ── #4 동적 타임스탑 ────────────────────────────────────────────────
        # 보유한도(max_hold_bars) 도달해도 (1) 의미있는 수익 + (2) 추세유지(20일선 위)
        # + (3) 최근 grace봉 내 신고가 갱신(추세가 살아있음) 이면 매도를 보류하고
        # 트레일링/손절에 위임한다. 정체·약세면 즉시 타임스탑. 무한 연장 방지를 위해
        # hard cap(max_hold_bars_hard)을 둔다.
        self.time_stop_extend   = True
        self.time_stop_band     = 0.02     # 정체 판정 수익밴드(이 이하면 정체로 보고 타임스탑)
        self.time_stop_grace    = 3        # 신고가 갱신이 이 봉수 이내여야 연장 허용
        self.max_hold_bars_hard = 20       # 연장 포함 절대 보유 한도

        # ── 하드코딩에서 변수화된 항목 ───────────────────────────────────
        self.obv_dead_min_bars  = 5        # OBV 데드크로스 노이즈 무시 봉수
        self.rsi_ideal_low      = 40       # RSI 신뢰구간 하한
        self.rsi_ideal_high     = 65       # RSI 신뢰구간 상한

        # ── 매수 필터 on/off 스위치 ─────────────────────────────────────
        # 각 매수 게이트를 개별적으로 켜고 끈다. False면 해당 필터를 건너뛴다.
        self.enable_macd_filter      = True  # macd_ok (양권/음권 급등/갭축소)
        self.enable_rsi_filter       = True  # 과매수(rsi>=overbought) 진입 차단
        self.enable_bb_upper_filter  = True  # BB 상단 추격 금지
        self.enable_vol_avg_filter   = True  # 20일 평균 거래량 이상
        self.enable_regime_gate      = True  # 적응형 추세국면 게이트

        # ── core 진입 신호 mode (MACD/OBV Optional) ─────────────────────
        # 각각 'off'(사용안함) / 'golden'(골든크로스 여부) / 'slope'(기울기 상승여부).
        #   기본값 'golden' = 기존 동작(MACD+OBV 동시 골든크로스)과 동일.
        #   both_now = macd_sig AND obv_sig. 둘 다 'off'면 core 조건 없이 필터만으로 진입.
        # freshness(신규신호 판정): golden mode는 직전 봉 크로스로 엄격 적용,
        #   slope mode는 직전 봉 기울기를 알 수 없어(prev_prev 미전달) 억제하지 않고
        #   cooldown_bars에 간격 제어를 위임한다.
        self.macd_signal_mode = 'slope'   # 'off' | 'golden' | 'slope'
        self.obv_signal_mode  = 'golden'   # 'off' | 'golden' | 'slope'

    def configure(self, user_info: UserOptionMeta) -> None:
        """user_options의 s1_* 값이 있으면 __init__ 기본값을 덮어씁니다."""
        def _f(val, cast=float):
            """None이 아니면 cast 변환해서 반환, None이면 None 반환"""
            return cast(val) if val is not None else None

        def _bool(val):
            """TINYINT(1) → bool 변환. None이면 None."""
            return bool(int(val)) if val is not None else None

        overrides = {
            'stop_loss_pct':          _f(user_info.s1_stop_loss_pct),
            'take_profit_pct':        _f(user_info.s1_take_profit_pct),
            'max_hold_bars':          _f(user_info.s1_max_hold_bars, int),
            'rsi_overbought':         _f(user_info.s1_rsi_overbought, int),
            'rsi_ideal_low':          _f(user_info.s1_rsi_ideal_low, int),
            'rsi_ideal_high':         _f(user_info.s1_rsi_ideal_high, int),
            'vol_ma_window':          _f(user_info.s1_vol_ma_window, int),
            'vol_ma_mult':            _f(user_info.s1_vol_ma_mult),
            'regime_window':          _f(user_info.s1_regime_window, int),
            'regime_threshold':       _f(user_info.s1_regime_threshold),
            'strict_need_macd_up':    _bool(user_info.s1_strict_need_macd_up),
            'loose_need_vol_surge':   _bool(user_info.s1_loose_need_vol_surge),
            'surge_relax_mult':       _f(user_info.s1_surge_relax_mult),
            'downtrend_surge_bypass': _bool(user_info.s1_downtrend_surge_bypass),
            'surge_bypass_mult':      _f(user_info.s1_surge_bypass_mult),
            'use_trailing':           _bool(user_info.s1_use_trailing),
            'trail_basis':            user_info.s1_trail_basis if user_info.s1_trail_basis else None,
            'trail_activate_pct':     _f(user_info.s1_trail_activate_pct),
            'k_trail_atr':            _f(user_info.s1_k_trail_atr),
            'trail_floor_pct':        _f(user_info.s1_trail_floor_pct),
            'time_stop_extend':       _bool(user_info.s1_time_stop_extend),
            'time_stop_band':         _f(user_info.s1_time_stop_band),
            'time_stop_grace':        _f(user_info.s1_time_stop_grace, int),
            'max_hold_bars_hard':     _f(user_info.s1_max_hold_bars_hard, int),
            'obv_dead_min_bars':      _f(user_info.s1_obv_dead_min_bars, int),
            # 매수 필터 on/off 스위치
            'enable_macd_filter':     _bool(user_info.s1_enable_macd_filter),
            'enable_rsi_filter':      _bool(user_info.s1_enable_rsi_filter),
            'enable_bb_upper_filter': _bool(user_info.s1_enable_bb_upper_filter),
            'enable_vol_avg_filter':  _bool(user_info.s1_enable_vol_avg_filter),
            'enable_regime_gate':     _bool(user_info.s1_enable_regime_gate),
            # core 진입 신호 mode
            'macd_signal_mode':       user_info.s1_macd_signal_mode if user_info.s1_macd_signal_mode else None,
            'obv_signal_mode':        user_info.s1_obv_signal_mode  if user_info.s1_obv_signal_mode  else None,
        }
        for attr, val in overrides.items():
            if val is not None:
                setattr(self, attr, val)

    def get_action(self, trade_data: list[dict], user_info: UserOptionMeta) -> Action:
        pass

    def get_action_with_prev(self, position_type: str, prev_info: UserCoinInfo, coin_info: UserCoinInfo, user_info: UserOptionMeta):
        self.configure(user_info)

        if position_type == 'watch':
            return self.get_action_in_watch(prev_info, coin_info, user_info)

        if position_type == 'active':
            return self.get_action_in_active(prev_info, coin_info, user_info)

        return None

    # ──────────────────────────────────────────────────────────────────
    # 매도 판별 (전량 매도 정책 / 분할 없음)
    #  우선순위: 1.손절(-5% or OBV 데드크로스) > 2.익절(+30%)
    #          > 3.트레일링(#1, 고점-k*ATR) > 4.동적 타임스탑(#4)
    #  포지션 상태(entry_price/bars_held/peak_close/bars_since_peak)는
    #  백테스트 엔진이 진입 시 세팅하고 매 봉 갱신해야 한다.
    # ──────────────────────────────────────────────────────────────────
    def get_action_in_active(self, prev_info: UserCoinInfo, coin_info: UserCoinInfo, user_info: UserOptionMeta) -> dict:
        close = coin_info.close
        entry = user_info.entry_price if user_info.entry_price > 0 else user_info.avg_price

        profit_pct = (close - entry) / entry if entry > 0 else 0.0
        stop_price = entry * (1 - self.stop_loss_pct)     # -5% 손절선
        target_price = entry * (1 + self.take_profit_pct) # +30% 익절선
        is_obv_dead = coin_info.obv_d_cross_n == 'D'      # OBV 데드크로스
        is_above_ema20 = close > coin_info.ema20 if coin_info.ema20 else False  # 20일선 위

        # OBV 데드크로스: 진입 후 obv_dead_min_bars 이내는 노이즈로 간주, 무시
        obv_dead_valid = is_obv_dead and user_info.bars_held >= self.obv_dead_min_bars

        # 가격 손절: -5% 하회하더라도 20일선 위에 있으면 유지
        price_stop_valid = (close <= stop_price) and not is_above_ema20

        # ── 트레일링(#1) 기준선 산출 ──────────────────────────────
        peak = (user_info.peak_close if self.trail_basis == 'close' else user_info.peak_high) \
               or close
        atr = float(coin_info.atr) if (coin_info.atr and float(coin_info.atr) > 0) \
              else float(user_info.entry_atr or 0)
        if atr > 0:
            trail_line = peak - self.k_trail_atr * atr          # 샹들리에: 고점 - k*ATR
        else:
            trail_line = peak * (1 - self.trail_floor_pct)      # ATR 미산출 대체: 고점 -10%
        peak_gain = (peak - entry) / entry if entry > 0 else 0.0
        trail_on = self.use_trailing and peak_gain >= self.trail_activate_pct
        trail_valid = trail_on and (close <= trail_line)

        # ── 1. 손절 (최우선) : 유효한 가격손절 또는 유효한 OBV 데드크로스 ──
        if price_stop_valid or obv_dead_valid:
            return self._build_sell(coin_info, user_info, Action.SELL_STOP_LOSS, profit_pct,
                                    stop_price, target_price,
                                    extra={'obv_dead': 'Y' if is_obv_dead else 'N',
                                           'obv_dead_valid': 'Y' if obv_dead_valid else 'N',
                                           'is_above_ema20': 'Y' if is_above_ema20 else 'N'})

        # ── 2. 익절 : +30% 도달 ───────────────────────────────────
        if close >= target_price:
            return self._build_sell(coin_info, user_info, Action.SELL_PROFIT, profit_pct,
                                    stop_price, target_price)

        # ── 3. 트레일링 스탑(#1) : 활성화 후 고점-k*ATR 하회 시 전량 청산 ──
        if trail_valid:
            return self._build_sell(coin_info, user_info, Action.SELL_TRAIL, profit_pct,
                                    stop_price, target_price,
                                    extra={'peak': round(peak, 2),
                                           'trail_line': round(trail_line, 2),
                                           'peak_gain': str(round(peak_gain * 100, 2)) + '%',
                                           'trail_basis': self.trail_basis})

        # ── 4. 동적 타임스탑(#4) : 보유한도 도달 시에만 평가 ───────────────
        #  추세 생존(수익+20일선 위+최근 신고가) 이면 보류→트레일/손절에 위임,
        #  정체·약세 또는 hard cap 초과면 즉시 타임스탑.
        if user_info.bars_held >= self.max_hold_bars:
            bars_since_peak = getattr(user_info, 'bars_since_peak', 0)
            trend_alive = (profit_pct > self.time_stop_band) and is_above_ema20 \
                          and (bars_since_peak <= self.time_stop_grace)
            over_hard = user_info.bars_held >= self.max_hold_bars_hard
            if self.time_stop_extend and trend_alive and not over_hard:
                # 매도 보류: 트레일링/손절이 청산을 책임진다
                return self._build_sell(coin_info, user_info, Action.HOLD, profit_pct,
                                        stop_price, target_price,
                                        extra={'time_stop': 'EXTENDED',
                                               'bars_since_peak': bars_since_peak})
            return self._build_sell(coin_info, user_info, Action.SELL_TIME, profit_pct,
                                    stop_price, target_price,
                                    extra={'bars_since_peak': bars_since_peak,
                                           'over_hard': 'Y' if over_hard else 'N'})

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

    def get_action_in_watch(self, prev_info: UserCoinInfo, coin_info: UserCoinInfo, user_info: UserOptionMeta) -> dict:
        result_action = Action.HOLD

        # ── 공통 지표 사전 계산 ────────────────────────────────────────────
        rate_str = str(round((coin_info.close - prev_info.close) / prev_info.close * 100, 2)) + "%" \
            if prev_info.close > 0 else "0%"

        # ── 핵심 신호: MACD/OBV 각각 mode(off/golden/slope) 조합 ──────────────
        is_macd_g = coin_info.macd_g_cross_n == 'G'
        is_obv_g  = coin_info.obv_g_cross_n  == 'G'
        macd_slope_up = float(coin_info.macd) > float(prev_info.macd)  # MACD 기울기 상승
        obv_slope_up  = float(coin_info.obv)  > float(prev_info.obv)   # OBV 기울기 상승

        # MACD 갭 축소 조건: 갭이 좁혀지는 중(크로스 임박) & 기울기 양수 (macd_ok 필터/지표용)
        curr_macd_gap = float(coin_info.macd) - float(coin_info.macd_s)
        prev_macd_gap = float(prev_info.macd)  - float(prev_info.macd_s)
        is_macd_gap_closing = (curr_macd_gap > prev_macd_gap) and \
                              (float(coin_info.macd) > float(prev_info.macd))
        is_macd_signal = is_macd_g or is_macd_gap_closing  # 지표(indicator)·참고용

        def _signal_ok(mode, is_golden, is_slope_up):
            """core 진입 신호 mode 판정. off=조건없음(통과)."""
            if mode == 'slope':  return is_slope_up
            if mode == 'off':    return True
            return is_golden     # 'golden'(기본)

        macd_sig = _signal_ok(self.macd_signal_mode, is_macd_g, macd_slope_up)
        obv_sig  = _signal_ok(self.obv_signal_mode,  is_obv_g,  obv_slope_up)
        both_now = macd_sig and obv_sig

        # freshness: 직전 봉이 이미 동일 core 신호 + 필터를 통과했으면 신규 아님.
        #   golden mode → 직전 봉 크로스 flag로 엄격 판정.
        #   slope mode  → 직전 봉 기울기 불가지(prev_prev 미전달) → False로 두어 억제하지 않음
        #                 (연속 재진입 간격은 cooldown_bars가 담당).
        #   off mode    → 조건 없음 → 직전에도 '통과'로 간주(True).
        def _prev_signal_ok(mode, prev_is_golden):
            if mode == 'slope':  return False   # 알 수 없음 → 억제 안 함
            if mode == 'off':    return True    # 조건 없음 → 중립(AND에 영향 X)
            return prev_is_golden               # 'golden'
        # core 신호가 하나도 없으면(둘 다 off) freshness 억제 대상이 없다 →
        # 매 봉 필터만으로 판정('그냥 허용'). 연속 재진입은 cooldown_bars가 담당.
        has_core_signal = (self.macd_signal_mode != 'off') or (self.obv_signal_mode != 'off')
        if has_core_signal:
            prev_macd_sig = _prev_signal_ok(self.macd_signal_mode, prev_info.macd_g_cross_n == 'G')
            prev_obv_sig  = _prev_signal_ok(self.obv_signal_mode,  prev_info.obv_g_cross_n  == 'G')
            both_prev = prev_macd_sig and prev_obv_sig
            prev_full_pass = both_prev \
                and (prev_info.rsi < self.rsi_overbought) \
                and (prev_info.close <= prev_info.bb_upper) \
                and ((prev_info.vol_avg <= 0) or (prev_info.volume >= prev_info.vol_avg * self.vol_ma_mult))
        else:
            prev_full_pass = False
        is_dual_fresh = both_now and not prev_full_pass

        # ── 보조 필터 ────────────────────────────────────────────────────
        candle_center = (coin_info.open + coin_info.close) / 2

        is_rsi_overbought  = coin_info.rsi >= self.rsi_overbought   # 과매수 진입 차단
        is_rsi_ideal       = self.rsi_ideal_low <= coin_info.rsi <= self.rsi_ideal_high  # 신뢰 구간
        is_macd_above_zero = coin_info.macd > 0                     # 상승추세 확인(0선 위)
        is_vol_surge       = coin_info.vol_surge_n > 0              # 거래량 급증(강화 신호)
        is_under_bb_upper  = coin_info.close <= coin_info.bb_upper  # 상단 추격 금지
        # 평균 거래량 기준 — 20일 평균 대비 이상이어야 진입 (종목 편차에 강함)
        is_vol_above_avg   = (coin_info.vol_avg <= 0) or \
                             (coin_info.volume >= coin_info.vol_avg * self.vol_ma_mult)
        # 음권 골든크로스 허용 조건: macd > macd_s(이미 골든크로스 상태) + 기울기 양수(전봉 대비 상승)
        is_macd_rising_fast = (coin_info.macd > coin_info.macd_s) and \
                              (coin_info.macd > prev_info.macd)
        # MACD 조건: 양권(0선 위) OR 음권이지만 빠르게 상승 중 OR 크로스 임박(갭 축소 중)
        macd_ok = is_macd_above_zero or is_macd_rising_fast or is_macd_gap_closing
        # 중기 추세 필터: ema20 > ema60 (상승 정렬). 매수 필수 조건.
        is_uptrend = bool(coin_info.ema20 and coin_info.ema60 and coin_info.ema20 > coin_info.ema60)

        # ── 적응형 추세국면 게이트 (구 is_uptrend 단일 게이트 대체) ──────────
        # 1) 국면 분류: 최근 N봉 중 close<ema60 비율로 하락국면 여부 판정
        dt_ratio = float(coin_info.downtrend_ratio or 0.0)
        is_downtrend_regime = dt_ratio >= self.regime_threshold

        above_ema20  = bool(coin_info.ema20 and coin_info.close > coin_info.ema20)
        above_ema60  = bool(coin_info.ema60 and coin_info.close > coin_info.ema60)
        ema_stack_up = is_uptrend                                   # ema20 > ema60
        macd_ge_sig  = float(coin_info.macd) >= float(coin_info.macd_s)

        # 거래량 급증(완화 기준): 당일 거래량 >= 전봉 거래량 * surge_relax_mult(기본 2배)
        #   3배짜리 vol_surge_n 이 못 잡는 2배대 돌파(예: 015760 01-12 ≈2.1배)를 보완
        prev_vol = float(prev_info.volume or 0)
        is_surge_relaxed = prev_vol > 0 and float(coin_info.volume) >= prev_vol * self.surge_relax_mult

        if is_downtrend_regime:
            # 하락국면 → 방어: 완전한 상승배열 + 모멘텀 확인된 경우만 진입(떨어지는 칼 차단)
            strict_ok = above_ema60 and ema_stack_up and (macd_ge_sig or not self.strict_need_macd_up)
            # 단, 거래량 급증(2배) 동반 + 단기선 위면 배열요건 면제하고 진입 허용(급반등 초입)
            surge_bypass = self.downtrend_surge_bypass and above_ema20 and is_surge_relaxed
            regime_gate = strict_ok or surge_bypass
            regime_label = 'DOWN'
        else:
            # 상승국면 → 수익 극대화: 단기선 위 + 거래량 급증(3배 vol_surge_n OR 완화 2배)
            #   → 3배에 못 미치는 돌파(예: 015760 01-12, 약 2.1배)도 포착
            regime_gate = above_ema20 and (is_vol_surge or is_surge_relaxed or not self.loose_need_vol_surge)
            regime_label = 'UP'

        # ── 공통 indicator 빌더 ───────────────────────────────────────────
        def _build_result(action: Action, extra: dict = None) -> dict:
            indicator = {
                'macd_cross':           coin_info.macd_g_cross_n,
                'obv_cross':            coin_info.obv_g_cross_n,
                'is_dual_cross':        'Y' if both_now              else 'N',
                'is_dual_fresh':        'Y' if is_dual_fresh         else 'N',
                'macd_mode':            self.macd_signal_mode,
                'obv_mode':             self.obv_signal_mode,
                'macd_sig':             'Y' if macd_sig              else 'N',
                'obv_sig':              'Y' if obv_sig               else 'N',
                'macd_slope_up':        'Y' if macd_slope_up         else 'N',
                'obv_slope_up':         'Y' if obv_slope_up          else 'N',
                'is_macd_signal':       'Y' if is_macd_signal        else 'N',
                'is_macd_gap_closing':  'Y' if is_macd_gap_closing   else 'N',
                'is_vol_above_avg':     'Y' if is_vol_above_avg      else 'N',
                'is_macd_above_zero':   'Y' if is_macd_above_zero    else 'N',
                'is_macd_rising_fast':  'Y' if is_macd_rising_fast   else 'N',
                'macd_ok':              'Y' if macd_ok               else 'N',
                'is_uptrend':           'Y' if is_uptrend            else 'N',
                'regime':               regime_label,
                'downtrend_ratio':      round(dt_ratio, 2),
                'regime_gate':          'Y' if regime_gate           else 'N',
                'is_surge_relaxed':     'Y' if is_surge_relaxed      else 'N',
                'is_under_bb_upper':    'Y' if is_under_bb_upper     else 'N',
                'is_vol_surge':         'Y' if is_vol_surge          else 'N',
                # 저장(DAO)용 지표 — 리팩터링 때 누락됐던 키 복구
                'is_vol_limit':         'Y' if coin_info.volume > user_info.vol_limit else 'N',  # 오늘 거래량 > user_options.vol_limit
                'is_over_on_mid':       'Y' if above_ema20           else 'N',  # 종가 > ema20(20일선 위)
                'is_bb_mid_breakout':   'Y' if (coin_info.bb_mid_breakout or 0) > 0 else 'N',    # bb_mid 돌파
                'is_rsi_ideal':         'Y' if is_rsi_ideal          else 'N',
                'is_rsi_overbought':    'Y' if is_rsi_overbought     else 'N',
                'rsi':                  round(coin_info.rsi, 2),
                'macd':                 round(float(coin_info.macd), 4),
                'macd_slope':           round(float(coin_info.macd) - float(prev_info.macd), 4),
                'macd_gap':             round(curr_macd_gap, 4),
                'macd_gap_delta':       round(curr_macd_gap - prev_macd_gap, 4),
            }
            if extra:
                indicator.update(extra)
            return {
                'stock_code': coin_info.coin_code,
                'stock_name': '',
                'action_type': action.name,
                'todayStock': {
                    'open':   coin_info.open,
                    'high':   coin_info.high,
                    'low':    coin_info.low,
                    'close':  coin_info.close,
                    'volume': coin_info.volume,
                    'rate':   rate_str,
                },
                'indicator': indicator,
            }

        # ── [core] MACD/OBV mode 조합 신호 (신선) ────────────────────────
        # macd_signal_mode·obv_signal_mode(off/golden/slope) 조합. 둘 다 off면
        # core 조건 없이(both_now=True) 아래 필터만으로 진입.
        if not is_dual_fresh:
            return _build_result(Action.HOLD)

        # ── [필터] 각 매수 기준을 enable_* 스위치로 개별 on/off ──────────────
        # MACD 조건 / 과매수 회피 / 상단 추격 금지 / 평균거래량
        if self.enable_macd_filter and not macd_ok:
            return _build_result(Action.HOLD)
        if self.enable_rsi_filter and is_rsi_overbought:
            return _build_result(Action.HOLD)
        if self.enable_bb_upper_filter and not is_under_bb_upper:
            return _build_result(Action.HOLD)
        if self.enable_vol_avg_filter and not is_vol_above_avg:
            return _build_result(Action.HOLD)

        # ── [추세국면 게이트] 구 is_uptrend 단일 게이트 대체 ──────────────────
        # 하락국면이면 엄격(상승배열+모멘텀), 상승국면이면 느슨(단기선 위+급등)만 통과.
        if self.enable_regime_gate and not regime_gate:
            return _build_result(Action.HOLD)

        # ── [진입] 거래량 급증 동반 시 BUY_SURGE, 아니면 BUY ──────────────
        result_action = Action.BUY_SURGE if is_vol_surge else Action.BUY
        return _build_result(result_action)