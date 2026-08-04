"""
backtestService.py — S1 전략 단일 종목 백테스트 (KospiStrategy1 위임)

라이브 OHLCV(KIS/yf)를 조회해 KisStockService.compute_indicator_df 로 지표를
계산한 뒤, user_options 의 s1_* 값을 UserOptionMeta 에 실어
KisBacktester + KospiStrategy1 으로 백테스트한다.

진입/청산 판단은 전부 KospiStrategy1 이 담당하며(기존 _simulate 인라인 로직 제거),
이 서비스는 데이터 준비와 위임만 한다. → /backtest/run 과 동일 엔진/결과 스키마.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.domains.vo.UserOptionMeta import UserOptionMeta
from app.ext_services.kis.KisEngine import KisEngine
from app.ext_services.yf.yfEngine import yfEngine
from app.services.kis.KisBacktester import KisBacktester
from app.services.kis.KisStockService import KisStockService
from app.services.kis.KospiStrategy import KospiStrategy1
from app.utils.constants.Literal import Literal

# compute_indicator_df 보조 윈도우 기본값.
# /backtest/ingest 의 _DEFAULT_USER_INFO_FOR_INGEST 와 동일하게 맞춰
# trade_candle_data 기반 /backtest/run 과 지표(cross 플래그·vol_surge 등)가 일관되게 한다.
_INGEST_VOL_SURGE         = 3.0
_INGEST_DELAY_DATE        = 5
_INGEST_MACD_RECENT_DAY   = 5
_INGEST_BB_OVER_RECENT_DAY = 5


class BacktestService:
    DEFAULT_FEE_RATE = 0.0015

    @staticmethod
    def _is_us(code: str) -> bool:
        return not (len(code) == 6 and code.isdigit())

    # ── user_options s1_* → UserOptionMeta ─────────────────────────────
    def _build_user_info(self, user_opts: dict | None) -> UserOptionMeta:
        """compute_indicator_df 용 윈도우 + s1_* 오버라이드를 실은 UserOptionMeta."""
        ui = UserOptionMeta()
        # 지표 계산 윈도우 (ingest 와 동일)
        ui.vol_surge          = _INGEST_VOL_SURGE
        ui.delay_date         = _INGEST_DELAY_DATE
        ui.macd_recent_day    = _INGEST_MACD_RECENT_DAY
        ui.bb_over_recent_day = _INGEST_BB_OVER_RECENT_DAY
        # user_options s1_* 오버라이드 → KospiStrategy1.configure 가 읽어 적용
        if user_opts:
            for k, v in user_opts.items():
                if hasattr(ui, k) and v is not None:
                    setattr(ui, k, v)
        return ui

    # ── 진입점 ─────────────────────────────────────────────────────────
    def run(self, stock_code: str, start_date: str, end_date: str,
            user_opts: dict | None) -> dict:
        ui = self._build_user_info(user_opts)

        # 지표 워밍업 확보: regime_window(s1) 또는 150봉 중 큰 값 + 여유 일수
        warmup = max(int(ui.s1_regime_window or 0), 150)
        fetch_start = (
            datetime.strptime(start_date, '%Y-%m-%d') - timedelta(days=warmup + 60)
        ).strftime('%Y-%m-%d')

        if self._is_us(stock_code):
            ohlcv = yfEngine().get_ohlcv(stock_code, fetch_start, end_date)
        else:
            ohlcv = KisEngine(virtual=False).getOHLCV(stock_code, fetch_start, end_date)

        if ohlcv is None or len(ohlcv) < 10:
            raise ValueError('INSUFFICIENT_DATA')


        print(ohlcv.tail(20))
        # 지표 계산 (워밍업 포함 전체 구간)
        df = KisStockService().compute_indicator_df(ohlcv.copy(), ui)
        df['ymd']      = df[Literal.YMD].astype(str)
        df['date']     = df['ymd'].str[:10]
        df['datetime'] = df['ymd']          # KisBacktester 리포트(entry_dt/exit_dt)용
        df = df.fillna(0.0)

        # 백테스트 구간으로 슬라이스 (지표 워밍업은 슬라이스 이전 구간에서 확보됨)
        sim = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
        if len(sim) < 5:
            raise ValueError('INSUFFICIENT_DATA')

        rows = sim.to_dict('records')

        backtester = KisBacktester(strategy=KospiStrategy1(), fee_rate=self.DEFAULT_FEE_RATE)
        return backtester.run_one(stock_code, rows, ui)
