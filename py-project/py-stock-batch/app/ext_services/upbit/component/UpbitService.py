import numpy as np
import pandas as pd
from scipy.signal import argrelextrema
import io, pytz, pprint, matplotlib, traceback

from app.common.constants.Literal import Literal
from app.domain.dao.userTestDao import UserTestDao

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from datetime import datetime, timedelta
from stock_shared.dao.userMasterDao import UserMasterDao
from app.domain.dto.userOptionMeta import UserOptionMeta

from stock_shared.vo.userCoinInfo import UserCoinInfo
from app.common.utils.mailTemplateUtils import mailUtils as mail
from app.common.utils.commUtils import _is_number_like, _fmt

kst = pytz.timezone("Asia/Seoul")
choices = ['G', 'D']
class UpbitService:
    ####################################################
    # __init__
    # - UserService init
    ####################################################
    def __init__(self):
        self.__name__ = 'UpbitService'
        self.userMasterDaoImpl = UserMasterDao()
        self.userTestDaoImpl = UserTestDao()


    ####################################################
    # compute_indicator_df
    # - OHLCV 데이터로 여러 지표 데이터 생성
    # - DF 다량건 업데이트용
    # - parameter
    #   - data
    ####################################################
    def compute_indicator_df(self, data:pd.DataFrame):
        ####################################################################
        # Constants
        ####################################################################
        bb_window = 20
        bb_window_avg = 30

        macd_window_long = 26
        macd_window_short = 12
        macd_window_signal = 9

        fs_lookback_window = 14
        fs_sma_window = 3

        roc_period = 12
        atr_period = 14
        rsi_period = 14
        rsi_signal_period = 9

        df_close = data[Literal.CLOSE].astype(float)
        df_high = data[Literal.HIGH].astype(float)
        df_low = data[Literal.LOW].astype(float)
        df_volume = data[Literal.VOLUME].astype(float)

        ####################################################################
        # 1. ema(지수가중 이동평균)
        ####################################################################
        data[Literal.EMA_20] = df_close.rolling(window=20).mean()
        data[Literal.EMA_60] = df_close.rolling(window=60).mean()
        data[Literal.EMA_120] = df_close.rolling(window=120).mean()

        def _rolling_slope(y: np.ndarray) -> float:
            # y: window 길이
            x = np.arange(len(y), dtype=float)
            y = y.astype(float)
            x_mean = x.mean()
            y_mean = y.mean()
            denom = ((x - x_mean) ** 2).sum()
            if denom <= 0:
                return 0.0
            return float(((x - x_mean) * (y - y_mean)).sum() / denom)

        # 1-1. ema120 slope
        data[Literal.EMA_120_SLOPE] = data[Literal.EMA_120].rolling(window=20, min_periods=20).apply(_rolling_slope, raw=True)


        ####################################################################
        # 2. Bollinger Band
        ####################################################################
        ma = df_close.rolling(bb_window).mean()
        std = df_close.rolling(bb_window).std(ddof=0)

        data[Literal.BB_MID] = ma
        data[Literal.BB_UPPER]  = ma + 2 * std
        data[Literal.BB_LOWER]  = ma - 2 * std
        data[Literal.BB_WIDTH]  = (data[Literal.BB_UPPER] - data[Literal.BB_LOWER]) / data[Literal.BB_MID] * 100
        data[Literal.BB_WIDTH_AVG] = data[Literal.BB_WIDTH].rolling(window=bb_window_avg).mean()
        data[Literal.BB_UPPER_CHK] = self.check_upper_than_bb_upper(df_high, data[Literal.BB_UPPER])
        data[Literal.BB_LOWER_CHK] = self.check_lower_than_bb_lower(df_low, data[Literal.BB_LOWER])


        ####################################################################
        # 3. MACD (12,26,9)
        ####################################################################
        data[Literal.MACD] = df_close.ewm(span=macd_window_short, adjust=False).mean() - df_close.ewm(span=macd_window_long, adjust=False).mean()
        data[Literal.MACD_S] = data[Literal.MACD].ewm(span=macd_window_signal, adjust=False).mean()
        data[Literal.MACD_LOWER_MEAN] = self.get_low_avg(data[Literal.MACD],'lower')
        data[Literal.MACD_UPPER_MEAN] = self.get_low_avg(data[Literal.MACD],'upper')

        data[Literal.MACD_RECENT_MIN] = data[Literal.MACD].rolling(window=7, min_periods=7).min()
        data[Literal.MACD_RECENT_MAX] = data[Literal.MACD].rolling(window=7, min_periods=7).max()

        ####################################################################
        # 4. Fast Stochastic
        ####################################################################
        lookback_low_min = df_low.rolling(window=fs_lookback_window).min() # 최근 Lookback 기간 최저가
        lookback_high_max = df_high.rolling(window=fs_lookback_window).max() # 최근 Lookback 기간 최고가
        data[Literal.FS_K] = (df_close - lookback_low_min) / (lookback_high_max - lookback_low_min) * 100
        data[Literal.FS_D] = data[Literal.FS_K].rolling(window=fs_sma_window).mean()


        ####################################################################
        # 5. roc
        ####################################################################
        shifted_close = df_close.shift(periods=roc_period)
        data[Literal.ROC] = (df_close - shifted_close) / shifted_close * 100


        ####################################################################
        # 6. 변동폭(TR, ATR)
        ####################################################################
        tr1 = df_high = df_low
        tr2 = (df_high - df_close.shift(periods=1)).abs()
        tr3 = (df_low - df_close.shift(periods=1)).abs()
        data[Literal.TR] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        data[Literal.ATR] = data[Literal.TR].ewm(alpha=1/atr_period, adjust=False).mean()
        data[Literal.ATR_PCT] = data[Literal.ATR] / df_close * 100


        ####################################################################
        # 8. RSI
        ####################################################################
        close_delta = df_close.diff()
        gain = close_delta.clip(lower=0.0)
        loss = (-close_delta).clip(lower=0.0)

        avg_gain = gain.ewm(alpha=1.0 / rsi_period, adjust=False, min_periods=rsi_period).mean()
        avg_loss = loss.ewm(alpha=1.0 / rsi_period, adjust=False, min_periods=rsi_period).mean()

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        # 정석 분기
        rsi = rsi.where(avg_loss != 0, 100.0)  # 손실 0이면 100
        rsi = rsi.where(avg_gain != 0, 0.0)  # 이익 0이면 0
        rsi = rsi.where(~((avg_gain == 0) & (avg_loss == 0)), 50.0)  # 둘다 0이면 50
        data[Literal.RSI] = rsi

        avg_gain = gain.ewm(alpha=1.0 / rsi_signal_period, adjust=False, min_periods=rsi_signal_period).mean()
        avg_loss = loss.ewm(alpha=1.0 / rsi_signal_period, adjust=False, min_periods=rsi_signal_period).mean()

        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        # 정석 분기
        rsi = rsi.where(avg_loss != 0, 100.0)  # 손실 0이면 100
        rsi = rsi.where(avg_gain != 0, 0.0)  # 이익 0이면 0
        rsi = rsi.where(~((avg_gain == 0) & (avg_loss == 0)), 50.0)  # 둘다 0이면 50
        data[Literal.RSI_SIGNAL] = rsi

        prev_rsi = data[Literal.RSI].shift(1)
        prev_rsi_signal = data[Literal.RSI_SIGNAL].shift(1)
        curr_rsi = data[Literal.RSI]
        curr_rsi_signal = data[Literal.RSI_SIGNAL]

        rsi_cond_golden = (prev_rsi < prev_rsi_signal) & (curr_rsi > curr_rsi_signal)
        rsi_cond_dead = (prev_rsi > prev_rsi_signal) & (curr_rsi < curr_rsi_signal)

        rsi_condition = [rsi_cond_golden, rsi_cond_dead]
        data[Literal.RSI_CROSS] = np.select(rsi_condition, choices, default = '')


        ####################################################################
        # volume
        # atr_pct와 bb_width는 둘 다 "크면 변동성 큼"이므로 간단 평균.
        ####################################################################
        # 필요 시 가중치 변경 가능. 추천받길 원함.
        data[Literal.VOL_RAW] = data[Literal.ATR_PCT] * 0.5 + data[Literal.BB_WIDTH] * 0.5
        data[Literal.VOL_RATIO] = df_volume / df_volume.tail(20).mean()
        data[Literal.VOL_LOW_TH] = data[Literal.VOL_RAW].rolling(window=120).quantile(0.25)
        data[Literal.VOL_HIGH_TH] = data[Literal.VOL_RAW].rolling(window=120).quantile(0.75)

        ####################################################################
        # OBV
        ####################################################################
        data[Literal.OBV] = (np.sign(df_close.diff()) * data[Literal.VOLUME]).fillna(0).cumsum()
        data[Literal.OBV_SIGNAL] = data[Literal.OBV].rolling(window=9).mean()

        prev_obv = data[Literal.OBV].shift(1)
        prev_signal = data[Literal.OBV_SIGNAL].shift(1)
        curr_obv = data[Literal.OBV]
        curr_signal = data[Literal.OBV_SIGNAL]

        # 1. 골든크로스 조건: 직전 캔들에서는 OBV가 Signal 이하 직후, 현재 캔들에서 위로 돌파
        cond_golden = (prev_obv < prev_signal) & (curr_obv > curr_signal)

        # 2. 데드크로스 조건: 직전 캔들에서는 OBV가 Signal 이상 직후, 현재 캔들에서 아래로 이탈
        cond_dead = (prev_obv > prev_signal) & (curr_obv < curr_signal)

        # 3. np.select로 조건에 따른 결과값 매핑
        conditions = [cond_golden, cond_dead]


        data[Literal.OBV_B] = data[Literal.OBV].shift(6)
        data[Literal.OBV_RECENT_MAX] = data[Literal.OBV].rolling(window=20).max()
        data[Literal.OBV_RECENT_MIN] = data[Literal.OBV].rolling(window=20).min()
        data[Literal.OBV_CROSS] = np.select(conditions, choices, default='')
        return data


    ####################################################
    # getChargImg
    # - mail에 그려넣을 차트 이미지 생성
    # - parameter
    #   - <DataFrame> data : 차트 데이터 200
    #   - <String> title : 차트 타이틀
    #   - <Bool> bb_on : 차트에 볼린져밴드 추가
    ####################################################
    def getChartImg(self, data, title=None, bb_on=False):
        up_color = '#e74c3c'
        down_color = '#4e9dff'
        body_width = 0.6
        wick_width = 0.8
        dpi = 160

        if data is None or data.empty:
            return None
        
        data = data.tail(120).copy()
        
        # -------- Plot 생성 --------
        x = np.arange(len(data)) # 균일 간격 인덱스
        times = data['Datetime'].values

        fig, ax = plt.subplots(figsize=(5, 4), dpi=160)
        # ax.plot(data['Datetime'], data['Close'], )
        ax.grid(True, linestyle='--', alpha=0.25)
        ax.set_xlabel('time', fontsize=10)
        ax.set_ylabel('price', fontsize=10)
        ax.vlines(
            x,
            data['Low'].values,
            data['High'].values,
            linewidth=wick_width,
            zorder=1
        )

        # 몸통
        up = data['Close'] >= data['Open']
        down = ~up

        def draw_bodies(mask, color):
            for xi, o, c in zip(x[mask], data.loc[mask, "Open"], data.loc[mask, "Close"]):
                y = min(o, c)
                h = abs(c - o)
                
                rect = Rectangle(
                    (xi - body_width / 2.0, y),
                    body_width,
                    h if h > 0 else 1e-9,  # 종가==시가일 때도 얇게 보이도록
                    facecolor=color,
                    edgecolor=color,
                    linewidth=0,
                    zorder=2,
                )
                ax.add_patch(rect)

        draw_bodies(up.values, up_color)
        draw_bodies(down.values, down_color)

        # -- Bollinger Band
        if bb_on and all(col in data.columns for col in ["BB_Upper", "BB_Middle", "BB_Lower"]):
            # 숫자 변환 + 유효 마스크
            upper = pd.to_numeric(data["BB_Upper"], errors="coerce")
            middle = pd.to_numeric(data["BB_Middle"], errors="coerce")
            lower = pd.to_numeric(data["BB_Lower"], errors="coerce")

            valid = ~(upper.isna() | lower.isna())
            if valid.any():
                ax.plot(x[valid], upper[valid], linewidth=1.2, label='BB Upper', zorder=3)
                ax.plot(x[valid], lower[valid], linewidth=1.2, label='BB Lower', zorder=3)

                ax.plot(x[~middle.isna()], middle[~middle.isna()], linewidth=1.0, linestyle='--', label='BB Mid', zorder=3)

                ax.legend(loc='upper left', fontsize=9)


        # X축을 실제 시간으로 라벨링 (인덱스→시간 포맷)
        ax.set_xlim(-0.5, len(data) - 0.5)
        locator = mdates.AutoDateLocator()
        formatter = mdates.ConciseDateFormatter(locator)
        # 보조 축을 만들어 시간 포맷만 표시 (메인 축은 인덱스 그대로)
        
        ax2 = ax.secondary_xaxis("bottom")
        step = max(1, len(x) // 8)
        t_parsed = [kst.localize(datetime.strptime(s, "%Y-%m-%d %H:%M:%S")) for s in times]
        t_sel = t_parsed[::step]
        
        ax2.set_xticks(x[::step])
        
        ax2.set_xticklabels(
            [dt.strftime("%m-%d %H:%M") for dt in t_sel]   # 직접 라벨 포맷팅(간단)
        )
        
        ax.set_ylabel("Price")
        if title:
            ax.set_title(title)

        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)

        return buf.read()




    ####################################################
    # send_mail
    ####################################################
    def create_mail_form(self, userInfo, upbit, coinDF):
        today = datetime.today()
        chartRange = (today - timedelta(hours=200)).strftime("%Y-%m-%dT%H-%M-%S")

        html = ''

        # 1. 현재 보유코인 현황
        balanceColumns = None #upbitConstant.upbit_balance_column
        balanceInfo = None #upbit.getCurrentWallet()['info']

        if balanceInfo:
            subTitle = mail.title("[UPBIT 현재 보유코인 현황]")
            
            bodyTrs = []
            for bInfo in balanceInfo:
                tds = []
                for col in balanceColumns:
                    val = bInfo.get(col['code'])
                    align = 'right' if _is_number_like(val) else 'center'
                    data = _fmt(f"{float(val):,}" if _is_number_like(val) else val)
                    tds.append(mail.td(data, align=align))

                bodyTrs.append(mail.tr(tds))

            balanceTable = mail.table(
                mail.thead(
                    mail.tr(
                        [mail.th(x['name']) for x in balanceColumns]
                    )   
                ),
                mail.tbody(
                    bodyTrs
                )
            )
            html = html + subTitle + balanceTable

                    #     # image
            #     b64 = base64.b64encode(self.upbitServiceImpl.getChartImg(computed, bb_on=True)).decode('ascii')
            #     html += f"""<div class="figure">
            #     <img src="data:image/png;base64,{b64}" alt="코인 차트 이미지">
            #     </div>"""

            # # 현재가
            # html = self.upbitServiceImpl.create_mail_form(userInfo, upbit).replace('\\n', '')
            # pprint.pprint(html)
            #emailUtils.sendMail("UPBIT MAIL", html, userInfo['email'])


        # 2. 코인 별 분석내용
        if coinDF:
            for key, df in coinDF.items():
                print(df)

        return html


    def get_low_avg(self, src: pd.Series, avg_type: str, window: int = 120, order: int = 5) -> pd.Series:
        # 1. 최근 데이터
        values = src.values
        real_index = None

        if avg_type == 'lower' :
            extrema_indexes = argrelextrema(values, np.less_equal, order=order)[0]
            real_index = extrema_indexes[values[extrema_indexes] < 0]

        elif avg_type == 'upper' :
            extrema_indexes = argrelextrema(values, np.greater_equal, order=order)[0]
            real_index = extrema_indexes[values[extrema_indexes] > 0]
        else :
            return pd.Series(0.0, index=src.index)

        # 3. 값 추출
        # iloc을 사용하여 인덱스 위치로 값 가져오기
        vertex_series = pd.Series(np.nan, index=src.index)
        vertex_series.iloc[real_index] = values[real_index]

        return vertex_series.rolling(window=window, min_periods=1).mean()


    def check_lower_than_bb_lower(self, df_close: pd.Series, df_bb_lower: pd.Series, window: int = 7) -> pd.Series:
        """
        최근 n(window)개 캔들 중, 종가(Close)가 볼린저 밴드 하단(BB_Lower)보다 낮았던 적이 있는지 확인
        :return: Boolean Series (True면 최근 n개 중 이탈 발생함)
        """
        # 1. 조건 비교 (Boolean Series 생성)
        # 종가가 밴드 하단보다 낮으면 True, 아니면 False
        is_below = df_close < df_bb_lower

        # 2. Rolling Max를 이용한 구간 체크
        # True는 1, False는 0으로 취급됩니다.
        # 최근 window 기간 중 최댓값이 1이라면, 한 번이라도 True가 있었다는 뜻입니다.
        # min_periods=1: 데이터가 window보다 적어도 있는 만큼만 계산
        was_below_recently = is_below.rolling(window=window, min_periods=1).max()

        # 3. 0.0/1.0을 다시 True/False로 변환하여 반환
        return was_below_recently


    def check_upper_than_bb_upper(self, df_close: pd.Series, df_bb_upper: pd.Series, window: int = 7) -> pd.Series:
        """
        최근 n(window)개 캔들 중, 종가(Close)가 볼린저 밴드 하단(BB_Lower)보다 낮았던 적이 있는지 확인
        :return: Boolean Series (True면 최근 n개 중 이탈 발생함)
        """
        # 1. 조건 비교 (Boolean Series 생성)
        # 종가가 밴드 하단보다 낮으면 True, 아니면 False
        is_below = df_close > df_bb_upper

        # 2. Rolling Max를 이용한 구간 체크
        # True는 1, False는 0으로 취급됩니다.
        # 최근 window 기간 중 최댓값이 1이라면, 한 번이라도 True가 있었다는 뜻입니다.
        # min_periods=1: 데이터가 window보다 적어도 있는 만큼만 계산
        was_below_recently = is_below.rolling(window=window, min_periods=1).max()

        # 3. 0.0/1.0을 다시 True/False로 변환하여 반환
        return was_below_recently














