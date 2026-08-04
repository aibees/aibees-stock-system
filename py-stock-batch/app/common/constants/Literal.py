

class Literal:
    OPEN = 'open'
    CLOSE = 'close'
    HIGH = 'high'
    LOW = 'low'
    VOLUME = 'volume'
    DATETIME = 'datetime'
    VOL_RATIO = 'vol_ratio'
    VOL_RAW = 'vol_raw'
    VOL_LOW_TH = 'vol_low_th'
    VOL_HIGH_TH = 'vol_high_th'
    VOL_SURGE_N = 'vol_surge_n'
    VOL_AVG = 'vol_avg'

    # Bollinger Band
    BB_UPPER = 'bb_upper'
    BB_UPPER_CHK = 'bb_upper_chk'
    BB_LOWER = 'bb_lower'
    BB_LOWER_CHK = 'bb_lower_chk'
    BB_MID = 'bb_mid'
    BB_WIDTH = 'bb_width'
    BB_WIDTH_AVG = 'bb_width_avg'
    BB_MID_BREAKOUT = 'bb_mid_breakout'
    RECENT_HIGH = 'recent_high'

    # 추세국면 분류기: 최근 N봉 중 close < ema60 비율 (0~1). 높을수록 하락국면.
    DOWNTREND_RATIO = 'downtrend_ratio'

    # EMA
    EMA_20 = 'ema20'
    EMA_60 = 'ema60'
    EMA_120 = 'ema120'
    EMA_120_SLOPE = 'ema120_slope'

    # HMA (Hull Moving Average) — KospiStrategy2 추세 코어
    HMA = 'hma'
    HMA_SLOPE = 'hma_slope'  # 당봉 hma - 전봉 hma (양수=상승전환)

    # 체결강도 (매수체결량/매도체결량*100, 100=균형).
    #  live: KIS inquire-ccnl(CTTR/STRN) 값 주입. backtest: OHLCV proxy(종가위치*200).
    CHEGYUL_STRENGTH = 'chegyul_strength'

    # MACD
    MACD = 'macd'
    MACD_S = 'macd_s'
    MACD_HIST = 'macd_hist'
    MACD_LOWER_MEAN = 'macd_lower_mean'
    MACD_UPPER_MEAN = 'macd_upper_mean'
    MACD_RECENT_MIN = 'macd_recent_min'
    MACD_RECENT_MAX = 'macd_recent_max'
    MACD_G_CROSS_N = 'macd_g_cross_n'
    MACD_D_CROSS_N = 'macd_d_cross_n'

    # ATR
    TR = 'tr'
    ATR = 'atr'
    ATR_PCT = 'atr_pct'

    # Fast Stochastic
    FS_K = 'fs_k'
    FS_D = 'fs_d'

    # ROC
    ROC = 'roc'
    RSI = 'rsi'
    RSI_SIGNAL = 'rsi_signal'
    RSI_CROSS = 'rsi_cross'

    # OBV
    OBV = 'obv'
    OBV_SIGNAL = 'obv_signal'
    OBV_B = 'obv_b'
    OBV_CROSS = 'obv_cross'
    OBV_EMA_SLOW = 'obv_ema_slow'
    OBV_RECENT_MIN = 'obv_recent_min'
    OBV_RECENT_MAX = 'obv_recent_max'
    OBV_G_CROSS_N = 'obv_g_cross_n'
    OBV_D_CROSS_N = 'obv_d_cross_n'

    # status
    ACTION_WATCH = 'WATCH'
    ACTION_ACTIVE = 'ACTIVE'


