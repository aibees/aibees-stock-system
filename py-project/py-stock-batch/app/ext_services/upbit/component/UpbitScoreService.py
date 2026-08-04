import pandas as pd
import numpy as np

from app.common.constants.Literal import Literal
from stock_shared.vo.userCoinInfo import UserCoinInfo
from app.domain.dto.userOptionMeta import UserOptionMeta
"""
momentum :: 
횡보장(ATR 낮음): Momentum 점수 비중 ↑ (오실레이터 매매)

추세장(ATR 높음): Trend 점수 비중 ↑ (추세 추종 매매)
"""
eps = 1e-8

class UpbitScoreService:
    # common def
    def float_clip(self, x: float, clip_min:float = 0.0, clip_max:float = 100.0) -> float:
        return float(np.clip(x, clip_min, clip_max))

    def signed_to_0_100(self, x: float, scale: float = 1.0) -> float:
        # x>0 => 50~100, x<0 => 0~50
        return self.float_clip(50.0 + 50.0 * np.tanh(float(x) * scale))

    # Trend Score 계산
    # - MACD 정규화 분모 불안정
    #   - macd_hist / abs(macd_s)는 macd_s가 0 근처면 스코어 폭주 위험
    #   - MACD 정규화 분모를 ATR/Close로 변경
    # - EMA 점수가 너무 계단식
    #   - spread와 기울기로 점수화
    # -결과는 "높을수록 상승추세(BULL), 낮을수록 하락추세(BEAR)"에 맞춤
    def get_indicator_score_trend(self, coin_info:UserCoinInfo):
        # Constants
        weight_macd = 0.45
        weight_ema = 0.35
        weight_slope = 0.20

        atr_denom = (coin_info.atr or 0) + eps

        if atr_denom < 1e-8:
            coin_info.score_trend = 50.0
            coin_info.sign_trend = 0.0
            return

        # =========================================================
        # (1) MACD 히스토그램 점수: macd_hist / ATR 정규화
        # =========================================================
        macd_hist = coin_info.macd - coin_info.macd_s # macd_hist = macd - macd signal
        macd_hist_norm = macd_hist / atr_denom
        macd_score = self.signed_to_0_100(macd_hist_norm, scale=15.5)

        # =========================================================
        # (2) EMA align 점수: (ema_fast-ema_mid), (ema_mid-ema_slow) 를 ATR로 정규화
        #     단순 "정렬되면 100"이 아니라 "정렬 강도"까지 반영
        # =========================================================
        spread_fm = (coin_info.ema20 - coin_info.ema60) / atr_denom
        spread_ms = (coin_info.ema60 - coin_info.ema120) / atr_denom

        # [-1,+1] 근사(포화)
        scale_of_ema = 10.0
        ema_align_raw = 0.5 * (np.tanh(spread_fm * scale_of_ema) + np.tanh(spread_ms * scale_of_ema))
        ema_score = self.float_clip(50.0 + 50.0 * ema_align_raw)

        # =========================================================
        # (3) Slope 점수: ema_slow의 롤링 선형회귀 slope / ATR
        #     pandas rolling + apply로 계산 (백테스트용, 충분히 빠름)
        # =========================================================

        slope_norm = coin_info.ema120_slope / atr_denom
        slope_score = self.signed_to_0_100(slope_norm, scale=40.0)

        # =========================================================
        # Trend 합성
        # =========================================================
        trend_score = round((
            weight_macd  * macd_score +
            weight_ema * ema_score +
            weight_slope * slope_score
        ), 2)

        # trend_sign: [-1,+1] 부드러운 방향값(게이트/confirm용)
        sign_raw = (
            weight_macd * np.tanh(macd_hist_norm * 15.0) +
            weight_ema * ema_align_raw +
            weight_slope * np.tanh(slope_norm * 40.0)
        )
        trend_sign = sign_raw.clip(-1.0, 1.0).round(4)

        coin_info.score_trend = trend_score
        coin_info.sign_trend = trend_sign


    def get_indicator_score_momentum(self, coin_info: UserCoinInfo, mode: str = "trend_follow"):
        # Constants
        weight_rsi = 0.3
        weight_stoch = 0.3
        weight_roc = 0.3

        overheat_rsi: float = 75.0
        overheat_stoch: float = 85.0
        overheat_strength: float = 18.0

        rsi_center: float = 50.0
        rsi_band: float = 10.0  # (rsi-50)/10
        rsi_scale: float = 1.2

        # ---- RSI score (안1 기본) ----
        # 과열을 “매수 점수”로 밀지 않게: 50 기준으로만 방향성 부여
        rsi_x = (coin_info.rsi - rsi_center) / (rsi_band + eps)
        rsi_score = self.signed_to_0_100(rsi_x, scale=rsi_scale)

        # ---- Stoch score (레벨 + 방향, 방향 비중↑) ----
        stoch_level = self.float_clip(coin_info.fs_k)  # 단순 레벨(0~100)
        # K-D 방향: K>D면 상승 모멘텀, K<D면 하락 모멘텀
        stoch_diff = self.signed_to_0_100((coin_info.fs_k - coin_info.fs_d) / 100.0, scale=4.5)
        # Stoch: 레벨보다 K-D 방향성 비중 확대
        stoch_score = 0.35 * stoch_level + 0.65 * stoch_diff

        # roc(%)를 ATR%(=atr/close*100)로 나눠 “변동성 대비 수익률”로 정규화
        atr_pct = (coin_info.atr / (coin_info.close + eps)) * 100.0
        roc_norm = coin_info.roc / (atr_pct + 1.0)  # 0 division 방지 + 과민반응 완화

        roc_score = self.signed_to_0_100(roc_norm, scale=1.2)

        base_momentum = (weight_rsi * rsi_score) + (weight_stoch * stoch_score) + (weight_roc * roc_score)

        # ---- mode별 보완 ----
        if mode == "trend_follow":
            # 안1: 과열 페널티 없이도, RSI/ROC를 “방향성” 중심으로 이미 정리됨
            coin_info.overheat_penalty = 0.0

        elif mode == "overheat_penalty":
            # 안2: 과열 구간 감점(횡보 상단에서 고RSI/고Stoch로 매수 되는 문제 완화)
            # - RSI>overheat_rsi, StochK>overheat_stoch 일수록 패널티 ↑
            # - 초과분을 0~1로 정규화 후 감점
            rsi_excess = (coin_info.rsi - overheat_rsi) / 10.0     # 10pt 초과를 1로
            k_excess = (coin_info.fs_k - overheat_stoch) / 10.0

            # 둘 중 하나만 과열이어도 패널티가 붙고, 둘 다면 더 커짐
            penalty_factor = self.float_clip((0.6 * rsi_excess + 0.4 * k_excess), 0.0, 2.0)
            overheat_penalty = self.float_clip((overheat_strength * penalty_factor), 0.0, 40.0)

            coin_info.overheat_penalty = overheat_penalty
            base_momentum = self.float_clip(base_momentum - overheat_penalty)

        else:
            raise ValueError("mode must be 'trend_follow' or 'overheat_penalty'")

        coin_info.score_momentum = self.float_clip(base_momentum)

    def get_indicator_score_volatility(self, coin_info: UserCoinInfo):
        """
        변동성 점수 (Volatility Expansion Model)
        - 목적: 변동성을 먹는 매매 (Trend Following / Breakout)
        - 로직:
            1. 변동성이 역사적 하단(Low) -> 상단(High)으로 갈수록 점수 상승
            2. High Threshold를 돌파(Expansion)하면 고득점 (80~100)
            3. Low Threshold 이하(Squeeze)는 점수는 낮지만 상태를 별도 기록 (관찰 필요)
        """

        # 1. vol_raw 계산 (BB Width + ATR%)
        # UserCoinInfo에 값이 없으면 즉석 계산
        if getattr(coin_info, 'vol_raw', 0.0) == 0.0:
            vol_raw = (coin_info.atr_pct * 0.5) + (coin_info.bb_width * 0.5)
        else:
            vol_raw = coin_info.vol_raw

        # 2. 임계값 가져오기 (120일 퀀타일)
        low_th = coin_info.vol_low_th  # 하위 25% (Squeeze 기준)
        high_th = coin_info.vol_high_th  # 상위 75% (Breakout 기준)
        eps = 1e-12

        # ---------------------------------------------------------
        # 3. 상태(State) 판별 (전략적 판단용)
        # ---------------------------------------------------------
        vol_state = "NORMAL"
        if vol_raw <= low_th:
            vol_state = "SQUEEZE"  # 에너지가 극도로 응축됨 (폭발 임박, 방향 미정)
        elif vol_raw >= high_th:
            vol_state = "EXPANSION"  # 변동성 폭발 중 (추세가 터짐)

        # ---------------------------------------------------------
        # 4. 점수 계산 (Expansion 지향)
        # ---------------------------------------------------------
        # 기본 아이디어: Low_th를 0점, High_th를 80점 기준으로 매핑
        # High_th를 넘어서면 100점을 향해 달려감

        # 구간의 너비
        range_width = (high_th - low_th) + eps

        # 현재 위치의 상대적 강도 (0.0 = Low_th, 1.0 = High_th)
        # vol_raw가 low_th보다 작으면 음수가 나올 수 있음 -> 0으로 보정하지 않고 그대로 둠(낮은 점수 유도)
        relative_strength = (vol_raw - low_th) / range_width

        # 점수 매핑 로직:
        # relative_strength < 0 (Squeeze) -> 0 ~ 20점 (아직 들어갈 때 아님)
        # relative_strength 0~1 (Normal)  -> 20 ~ 80점 (서서히 달아오름)
        # relative_strength > 1 (High)    -> 80 ~ 100점 (변동성 파티)

        # tanh를 사용하여 부드러운 S커브 적용
        # 중심을 0.5(Normal 중간)에 두고 스케일링
        # relative_strength가 1.0일 때 -> score가 약 80점이 되도록 튜닝

        # 수식: (Strength * Factor)를 Sigmoid 태움
        # 여기서는 직관적인 선형 보간 + tanh 마감 사용

        # 1. Base Score: 0.0~1.0 구간을 20~80점으로 매핑
        base_score = 20.0 + (relative_strength * 60.0)

        # 2. Squeeze 보정: 너무 낮으면(음수) 최소 5점은 유지 (완전 0점은 데이터 오류 같으니)
        if base_score < 20.0:
            # Squeeze 구간: 5~20점 사이
            # Squeeze가 심할수록(변동성 없을수록) 점수가 낮음 -> "먹을 게 없다"
            base_score = max(5.0, base_score)

        # 3. Expansion 보정: 1.0 넘어가면 80~100점 구간으로 진입
        elif base_score > 80.0:
            # 초과분을 tanh로 눌러담아 100점을 넘지 않게 포화시킴
            excess = base_score - 80.0
            # excess가 커질수록 20점에 수렴하여 더해짐
            added = 20.0 * np.tanh(excess / 20.0)
            base_score = 80.0 + added

        trend_factor = abs(getattr(coin_info, 'sign_trend', 0.0))

        # 최소한의 기본 점수(예: 40점)는 보장하되, 고득점은 trend가 받쳐줘야 가능하게 변경
        # (trend_factor가 작으면 base_score가 아무리 높아도 깎임)
        adjusted_vol_score = base_score * (0.4 + 0.6 * trend_factor)

        coin_info.score_volatility = self.float_clip(adjusted_vol_score)
        coin_info.state_volatility = vol_state

    def get_indicator_score_volume(self, coin_info: UserCoinInfo):
        """
        df 전체에 volume score(0~100)를 추가합니다.
        - OBV는 (EMA_fast - EMA_slow) 기반으로 안정화
        - vol_ratio는 방향화(trend_sign 곱)하지 않고 '확인(활동성)' 점수로 사용
        """
        # Constants
        weight_obv = 0.7
        weight_vol = 0.3

        # ---------------------------------------------------------
        # (1) OBV Flow Score (수급의 질)
        # ---------------------------------------------------------
        # OBV Cross(Fast-Slow)를 Slow의 절대값으로 나누어 정규화
        # OBV 값이 클수록 Cross 값도 커지는 스케일 문제를 해결
        # coin_info에 obv_cross와 obv_ema_slow가 계산되어 있어야 함

        obv_slow_abs = abs(coin_info.obv_ema_slow) + eps
        obv_norm = 0

        # scale=3.0: OBV 괴리율이 0.1(10%) 정도면 tanh(0.3) -> 의미있는 점수 변동
        # 상황에 따라 scale 튜닝 가능 (대형주는 낮게, 잡코인은 높게)
        score_obv = self.signed_to_0_100(obv_norm, scale=4.5)

        # ---------------------------------------------------------
        # (2) Volume Ratio Score (수급의 양/강도)
        # ---------------------------------------------------------
        # vol_ratio = 현재볼륨 / 이평볼륨
        # 1.0(평균) -> 50점
        # 2.0(2배)  -> tanh(1.25) -> 약 92점 (강한 거래량 실림)
        # 0.5(반토막)-> tanh(-0.625) -> 약 22점 (거래량 죽음)

        vr = coin_info.vol_ratio
        # 중심값 1.0을 0으로 이동시킨 후 tanh 스케일링
        score_vol_confirm = self.float_clip(50.0 + 50.0 * np.tanh((vr - 1.0) * 1.25))

        # ---------------------------------------------------------
        # (3) 합성
        # ---------------------------------------------------------
        # 가중치 정규화 (혹시 모를 합계 오류 방지)
        w_total = weight_obv + weight_vol
        final_score = (
                (weight_obv / w_total) * score_obv +
                (weight_vol / w_total) * score_vol_confirm
        )

        coin_info.score_volume = self.float_clip(final_score)


    def get_final_strategy(self, coin_info: UserCoinInfo):
        """
        최종 스코어링 및 매매 전략 수립
        - 목적: 변동성 돌파 + 추세 추종
        - 특징: Trend 방향이 맞고 Volatility가 터질 때 점수 극대화
        """

        # 1. 기본 가중치 설정 (변동성 매매 맞춤형)
        # Trend(방향)와 Volatility(에너지)가 가장 중요
        w_trend = 0.30
        w_volatility = 0.30
        w_momentum = 0.25
        w_volume = 0.15

        # 점수 가져오기 (None 방지용 0.0 처리)
        s_trend = getattr(coin_info, 'score_trend', 0.0)
        s_vol = getattr(coin_info, 'score_volatility', 0.0)
        s_mom = getattr(coin_info, 'score_momentum', 0.0)
        s_volume = getattr(coin_info, 'score_volume', 0.0)

        state_vol = getattr(coin_info, 'state_volatility', 'NORMAL')
        penalty = getattr(coin_info, 'overheat_penalty', 0.0)

        # ---------------------------------------------------------
        # 2. Gatekeeper: 추세 방향성 체크
        # ---------------------------------------------------------
        # 하락 추세(-1.0 ~ 0.0)인 경우 롱 포지션 진입 금지
        # 0.2 미만은 '추세 없음' 또는 '약한 상승'으로 보아 보수적 접근

        # ---------------------------------------------------------
        # 3. Base Score 계산 (가중 평균)
        # ---------------------------------------------------------
        base_score = (
                (s_trend * w_trend) +
                (s_vol * w_volatility) +
                (s_mom * w_momentum) +
                (s_volume * w_volume)
        )

        # ---------------------------------------------------------
        # 4. Contextual Adjustment (상황별 점수 보정)
        # ---------------------------------------------------------

        # A. 변동성 상태에 따른 보정 (핵심)
        # EXPANSION: 변동성 돌파 매매의 핵심 구간 -> 가산점 부여 (최대 1.2배)
        if state_vol == "EXPANSION":
            base_score *= 1.15
            # SQUEEZE: 에너지가 너무 죽어있음 -> 감점 (0.8배)
        elif state_vol == "SQUEEZE":
            base_score *= 0.8

        # B. 거래량(수급) 거부권
        # 거래량 점수가 20점 미만이면 '허수'일 가능성 높음 -> 점수 반토막
        if s_volume < 20.0:
            base_score *= 0.5

        # C. 과열 페널티 적용 (Momentum 단계에서 계산된 값 차감)
        final_score = base_score - penalty

        # 최종 클리핑 (0~100)
        final_score = self.float_clip(final_score)
        coin_info.score = round(final_score, 2)
        # print("coin score : ", coin_info.score)

        # ---------------------------------------------------------
        # 5. Action Strategy (매매 판단)
        # ---------------------------------------------------------
        # 점수 구간별 행동 정의

        action = "WAIT"
        regime = "NEUTRAL"

        # 구간 기준선 (Thresholds)
        # 변동성 돌파는 신호가 강할 때만 들어가야 함 -> 기준을 높게 설정
        th_strong_buy = 85.0
        th_buy = 70.0
        th_watch = 50.0

        if final_score >= th_strong_buy:
            action = "STRONG_BUY"
            regime = "BULL_RALLY"
        elif final_score >= th_buy:
            action = "BUY"
            regime = "BULL_START"
        elif final_score >= th_watch:
            # 점수는 애매한데 추세가 살아있거나, Squeeze 중일 수 있음
            if state_vol == "SQUEEZE":
                action = "WATCH_BREAKOUT"  # 곧 터질지 모름
            else:
                action = "HOLD"  # 기존 보유자는 홀딩, 신규는 대기
            regime = "WATCH"
        else:
            # 50점 미만
            action = "SELL"  # 하락 반전 가능성sfas

        # 추가 로직: "이미 너무 과열이면 추격 매수 금지"
        # 점수는 높게 나오지만 penalty가 컸다면 -> 이익 실현 구간
        if penalty > 20.0 and action in ["BUY", "STRONG_BUY"]:
            action = "PROFIT_TAKE"  # 매수보다는 분할 매도 권장

        coin_info.action = action
        coin_info.regime = regime
