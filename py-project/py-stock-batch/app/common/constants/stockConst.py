from app.common.constants.Literal import Literal


class StockConst:
    def __init__(self):
        self.field_map_kis = {
        'open': Literal.OPEN,
        'high': Literal.HIGH,
        'low': Literal.LOW,
        'close': Literal.CLOSE,
        'volume': Literal.VOLUME,
        'vol_surge_n': Literal.VOL_SURGE_N,
        'datetime': Literal.DATETIME,
        # --- 지표 ---
        'ema20': Literal.EMA_20,
        'ema60': Literal.EMA_60,
        'ema120': Literal.EMA_120,

        'bb_mid': Literal.BB_MID,
        'bb_lower': Literal.BB_LOWER,
        'bb_lower_chk': Literal.BB_LOWER_CHK,
        'bb_upper': Literal.BB_UPPER,
        'bb_upper_chk': Literal.BB_UPPER_CHK,
        'bb_mid_breakout': Literal.BB_MID_BREAKOUT,

        'macd': Literal.MACD,
        'macd_s': Literal.MACD_S,
        'macd_lower_mean': Literal.MACD_LOWER_MEAN,
        'macd_upper_mean': Literal.MACD_UPPER_MEAN,
        'macd_recent_min': Literal.MACD_RECENT_MIN,
        'macd_recent_max': Literal.MACD_RECENT_MAX,
        'macd_g_cross_n': Literal.MACD_G_CROSS_N,
        'macd_d_cross_n': Literal.MACD_D_CROSS_N,

        'obv': Literal.OBV,
        'obv_signal': Literal.OBV_SIGNAL,
        'obv_g_cross_n': Literal.OBV_G_CROSS_N,
        'obv_d_cross_n': Literal.OBV_D_CROSS_N
    }

stockConst = StockConst()