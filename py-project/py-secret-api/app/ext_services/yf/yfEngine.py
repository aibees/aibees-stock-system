from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from app.utils.constants.Literal import Literal


class yfEngine:
    """
    yFinance 기반 미국 주식 OHLCV 조회 엔진.
    KisEngine과 동일한 반환 스펙(ymd, open, high, low, close, volume)을 따릅니다.
    """

    def __init__(self):
        pass

    # ── 내부 헬퍼 ────────────────────────────────────────────

    @staticmethod
    def _produce_data(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # DatetimeIndex → ymd 컬럼
        if df.index.tz is not None:
            df.index = df.index.tz_convert("America/New_York")
        df[Literal.YMD] = df.index.strftime("%Y-%m-%d %H:%M:%S")

        # yfinance 컬럼명 소문자 통일
        df = df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })

        df["open"]   = df["open"].round(2)
        df["high"]   = df["high"].round(2)
        df["low"]    = df["low"].round(2)
        df["close"]  = df["close"].round(2)
        df["volume"] = df["volume"].astype(int)

        return df[[Literal.YMD, "open", "high", "low", "close", "volume"]].reset_index(drop=True)

    # ── 공개 메서드 ──────────────────────────────────────────

    # KisEngine과 동일한 단위 → (캔들당 캘린더 일수 배수, yfinance interval) 매핑
    _UNIT_MAP = {
        "day":   (1.8, "1d"),
        "week":  (7.5, "1wk"),
        "month": (31,  "1mo"),
        "year":  (366, "3mo"),  # yfinance는 연봉 미지원 → 분기봉으로 근사
    }

    def get_ohlcv_period(self, code: str, period: int = 200) -> pd.DataFrame | None:
        """
        오늘 기준 최근 period 거래일의 일봉 OHLCV를 반환합니다. (기본)
        """
        return self.get_ohlcv_period_unit(code, period, unit="day")

    def get_ohlcv_period_unit(
        self, code: str, period: int = 200, unit: str = "day"
    ) -> pd.DataFrame | None:
        """
        일/주/월/년 단위 OHLCV 캔들을 period개(근사) 반환합니다.
        KisEngine.get_ohlcv_period_unit과 동일한 인터페이스.
        """
        unit = (unit or "day").lower()
        if unit not in self._UNIT_MAP:
            raise ValueError(
                f"지원하지 않는 unit='{unit}'. (day|week|month|year 중 하나)"
            )
        factor, interval = self._UNIT_MAP[unit]
        try:
            window_days = int(float(period) * factor)
            start = (datetime.today() - timedelta(days=window_days)).strftime("%Y-%m-%d")
            df = yf.Ticker(code).history(start=start, interval=interval, auto_adjust=True)
            if df.empty:
                return None
            return self._produce_data(df).tail(period).reset_index(drop=True)
        except Exception:
            return None

    def get_ohlcv(self, code: str, start_date: str, end_date: str) -> pd.DataFrame | None:
        """
        날짜 범위(YYYY-MM-DD)의 OHLCV를 반환합니다.
        yfinance end는 exclusive이므로 하루 더해서 요청합니다.
        """
        try:
            end_exclusive = (
                datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            ).strftime("%Y-%m-%d")
            df = yf.Ticker(code).history(start=start_date, end=end_exclusive, auto_adjust=True)
            if df.empty:
                return None
            return self._produce_data(df)
        except Exception:
            return None
