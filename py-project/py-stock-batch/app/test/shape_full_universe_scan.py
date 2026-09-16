"""
테스트용 배치: KospiStrategy1 게이트를 거치지 않은 "진짜 전종목"(market_stop 활성 +
group_code in ST/RT/MF, get_stock_master_list('batches')와 동일 대상)을 스캔해서
shape_proba(OLD/NEW 두 모델)를 계산하고 trade_shape_scan_stock 에 저장한다.

trade_candle_data 는 TradeCandleBackfillJob이 "최근 60일 내 한 번이라도 추천된 종목"만
채우기 때문에, 그걸로 만든 raw-universe 백테스트는 이미 old_score(=KospiStrategy1 게이트)
쪽으로 편향돼 있었다 — 이 스캔은 그 편향을 없애기 위해 진짜 전종목 시세를 새로 받는다.

실행: 종목당 KIS API 호출 1.5초 슬립 → 전체 ~3,900종목 기준 1시간 이상 소요.
      순차 실행(스레드 분할 없음, rate limit 안전 우선). 중간 실패는 skip하고 계속 진행.

수동 실행:
    cd py-project/py-stock-batch && ./.venv/bin/python3 -m app.test.shape_full_universe_scan
"""
import sys
import time
from datetime import datetime, timedelta

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.mysql import insert as mysql_insert

sys.path.insert(0, '../shared')

from stock_shared.db.database import dbConn
from stock_shared.dto.userOptionMeta import UserOptionMeta
from stock_shared.ml.shape_features import SHAPE_FEATURE_COLUMNS
import stock_shared.ml.shape_model as sm
from app.ext_services.kis.KisEngine import KisEngine
from app.ext_services.kis.component.KisStockService import KisService
from app.batches.services.stockService import StockService

DB_URL = 'mysql+pymysql://stock:stock123!!@210.103.60.108:3333/stock'
OLD_MODEL_PATH = '/private/tmp/claude-501/-Users-user-Documents-workspace3-aibees-stock-system/292f8954-73d8-41bb-9322-4286a25cc597/scratchpad/shape_gbm_v1_OLD.joblib'
OLD_FEATURE_COLS = [
    'shape_total_ret_14', 'shape_min_ret_14', 'shape_bars_since_min',
    'shape_recovery_from_min', 'shape_early_ret_9', 'shape_late_ret_5',
    'shape_down_ratio_14', 'shape_path_std_14', 'shape_vol_trend',
]
NEW_FEATURE_COLS = SHAPE_FEATURE_COLUMNS  # 위 9개 + ind_rsi14/ind_macd_hist_norm/ind_vol_ratio_today

SLEEP_SEC = 1.5
MIN_DAYS = 250
START_DATE = '2025-06-01'   # 7~8월 라벨(net_edge_fwd) 계산 + shape lookback 여유
END_DATE = datetime.now().strftime('%Y-%m-%d')
SAVE_FROM = '2026-06-01'    # 이 날짜 이후 행만 DB에 저장(용량 절약, 학습용 임베고 여유는 둠)


def compute_net_edge_fwd(g: pd.DataFrame, window: int = 5) -> pd.Series:
    """base=당일 종가. 향후 window 거래일의 high 최대/low 최소로 gain/loss 산출."""
    n = len(g)
    close = g['close'].astype(float).values
    high = g['high'].astype(float).values
    low = g['low'].astype(float).values
    out = np.full(n, np.nan)
    for i in range(n - window):
        base = close[i]
        if base <= 0:
            continue
        fwd_high = high[i + 1:i + 1 + window]
        fwd_low = low[i + 1:i + 1 + window]
        if len(fwd_high) < window:
            continue
        gain_pct = (fwd_high.max() - base) / base * 100
        loss_pct = (base - fwd_low.min()) / base * 100
        out[i] = gain_pct - loss_pct
    return pd.Series(out, index=g.index)


def main():
    engine = create_engine(DB_URL, pool_pre_ping=True)
    session = dbConn.get_session()

    old_model = joblib.load(OLD_MODEL_PATH)

    stock_service = StockService()
    targets = stock_service.get_stock_master_list(session, 'batches')
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if limit:
        targets = targets[:limit]
    print(f"[대상] {len(targets)}종목 (market_stop 활성 + ST/RT/MF, limit={limit})", flush=True)

    kis_service = KisService()
    kis_engine = KisEngine()

    dummy_ui = UserOptionMeta()
    dummy_ui.vol_limit = 0
    dummy_ui.vol_surge = 3.0
    dummy_ui.delay_date = 5
    dummy_ui.macd_recent_day = 20
    dummy_ui.bb_over_recent_day = 7

    ok, fail, skip, total_rows = 0, 0, 0, 0
    t0 = time.time()

    for idx, stock in enumerate(targets):
        code = stock.get('stock_code')
        name = stock.get('stock_name') or code
        try:
            time.sleep(SLEEP_SEC)
            ohlcv = kis_engine.get_daily_ohlcv(code, START_DATE, END_DATE, min_days=MIN_DAYS)
            if ohlcv is None or len(ohlcv) < 2:
                skip += 1
                continue

            data = kis_service.compute_indicator_df(ohlcv, user_info=dummy_ui)
            data['datetime'] = pd.to_datetime(data['datetime'])
            data['net_edge_fwd'] = compute_net_edge_fwd(data)

            data['shape_proba_old'] = np.nan
            data['shape_proba_new'] = np.nan
            valid = data.dropna(subset=OLD_FEATURE_COLS)
            if len(valid):
                Xo = valid[OLD_FEATURE_COLS].values
                data.loc[valid.index, 'shape_proba_old'] = old_model.predict_proba(Xo)[:, 1]
            valid_new = data.dropna(subset=NEW_FEATURE_COLS)
            if len(valid_new):
                Xn = valid_new[NEW_FEATURE_COLS].values
                # 배포된(신규 학습) 모델 재사용 — stock_shared.ml.shape_model 과 동일 아티팩트
                sm._load()
                data.loc[valid_new.index, 'shape_proba_new'] = sm._model.predict_proba(Xn)[:, 1]

            save_df = data[data['datetime'] >= pd.Timestamp(SAVE_FROM)].copy()
            if save_df.empty:
                skip += 1
                continue

            cols = ['datetime', 'open', 'high', 'low', 'close', 'volume', 'ema20', 'ema60',
                    'macd', 'macd_s', 'rsi', 'atr', 'recent_high', 'bb_mid_breakout', 'vol_avg'] + \
                   NEW_FEATURE_COLS + ['shape_proba_old', 'shape_proba_new', 'net_edge_fwd']
            save_df = save_df[cols].replace([np.inf, -np.inf], np.nan)
            save_df['datetime'] = save_df['datetime'].astype(str)
            save_df.insert(0, 'coin', code)
            records = [
                {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in rec.items()}
                for rec in save_df.to_dict(orient='records')
            ]

            with engine.begin() as conn:
                for rec in records:
                    cols_sql = ', '.join(rec.keys())
                    vals_sql = ', '.join(f':{k}' for k in rec.keys())
                    update_sql = ', '.join(f'{k}=VALUES({k})' for k in rec.keys() if k not in ('coin', 'datetime'))
                    sql = f"INSERT INTO trade_shape_scan_stock ({cols_sql}) VALUES ({vals_sql}) " \
                          f"ON DUPLICATE KEY UPDATE {update_sql}"
                    conn.execute(text(sql), rec)

            ok += 1
            total_rows += len(records)
            elapsed = time.time() - t0
            eta_min = (elapsed / (idx + 1)) * (len(targets) - idx - 1) / 60
            print(f"[{idx+1}/{len(targets)}] {name}({code}) {len(records)}행 저장 "
                  f"(누적 {total_rows}행, 경과 {elapsed/60:.1f}분, 예상잔여 {eta_min:.1f}분)", flush=True)

        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"[{idx+1}/{len(targets)}] {name}({code}) 실패: {e}", flush=True)
            continue

    print(f"\n[완료] 성공 {ok} / 스킵 {skip} / 실패 {fail} / 총 저장행 {total_rows} "
          f"(총 소요 {(time.time()-t0)/60:.1f}분)", flush=True)


if __name__ == '__main__':
    main()
