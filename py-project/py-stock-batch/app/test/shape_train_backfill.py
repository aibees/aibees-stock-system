"""과거 일봉을 KIS 로 재조회해 trade_shape_train_daily 학습셋을 백필하는 1회성 스크립트.

왜 필요한가
    적재(StockBuyCheckJob)는 2026-10-01 시점에 0행이었다 — 16_shape_train_daily_ddl.sql
    이 운영 DB 에 적용되지 않은 채로 코드만 배포돼 있었고, 적재부가 fail-soft 라
    매일 조용히 실패하고 있었다. 앞으로 하루 한 날짜씩 쌓이길 기다리면 주말 학습
    배치(ShapeTrainJob)가 몇 주간 "데이터 부족"으로 스킵만 한다. 그 공백을 메운다.

왜 기존 trade_shape_scan_stock 을 쓰지 않는가
    그 테이블(19.9만행, 2026-06~09)에는 obv_gap_norm / obv_slope3 가 없다 —
    OBV 2종이 추가되기 전 스캔 결과라 12피처뿐이다. 현재 모델은 14피처이므로
    그대로는 학습 입력이 못 된다. 그래서 일봉을 다시 받아 14피처를 전부 계산한다.

라벨은 채우지 않는다
    net_edge_fwd 는 이 스크립트가 계산하지 않고 **ShapeLabelJob 에 맡긴다**.
    이 스크립트가 OHLCV(open/high/low/close/volume)를 같이 적재하므로 라벨은
    테이블 안에서 자기완결적으로 계산된다. 라벨 식을 여기 한 번 더 복제하면
    shape_label.py 단일 출처가 깨진다(학습 라벨과 평가 라벨이 갈리는 그 사고).
    → 백필 후 반드시:  POST /api/v1/jobs/once/SHAPE_LABEL_JOB
                       {"since": "<START_SAVE_FROM>", "lookback_days": 9999}

유니버스 필터 (일별 적재와 일치시킴)
    StockBuyCheckJob 은 거래량(user_options.vol_limit)·종가(1,000원) 필터를 학습셋
    적재보다 **앞단**에서 적용한다. 그래서 일별로 쌓이는 학습셋은 '전종목'이 아니라
    '통과분'이고(2026-10-01 실측 11.6%), 라이브 추론도 같은 루프 안이라 통과분에만
    계산된다. 백필도 같은 기준을 써야 학습분포와 추론분포가 일치한다.
    적용 단위는 **봉별**이다 — 그 날 라이브였다면 포함됐는지를 날짜별로 재현한다.
    단 피처 계산은 필터 적용 전 전체 시계열로 한다(lookback 에 구멍이 생기면 안 된다).

채우지 않는 컬럼과 그 이유
    shape_proba_at_scan  "그날 라이브 모델이 실제로 낸 값"이라는 정의라서, 오늘의
                         모델로 소급 채점하면 의미가 정반대가 된다(드리프트 감시용
                         기준선이 사라진다). NULL 로 둔다.
    composite_eligible   _composite_eligible 은 StockBuyCheckJob 내부 판정이고
    action_type          그날의 user_options 상태에 의존한다. 소급 재현 불가 → NULL.
    셋 다 학습 입력이 아니라 오프라인 평가용 컬럼이므로 NULL 이어도 학습에 지장 없다.

소요시간 / 안전성
    종목당 KIS 호출 1회 + 1.5초 슬립 → 2,700종목 기준 약 70분. 순차 실행(스레드 분할
    없음, rate limit 안전 우선). 중간 실패는 skip 하고 계속 진행한다.
    --resume 은 이미 적재된 종목을 건너뛰므로 중단 후 재실행이 싸다.

실행
    cd py-project/py-stock-batch
    ./.venv/bin/python3 -m app.test.shape_train_backfill --save-from 2026-06-01
    ./.venv/bin/python3 -m app.test.shape_train_backfill --limit 5 --dry-run   # 먼저 소량 점검
"""
import argparse
import sys
import time
from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy import text

sys.path.insert(0, '../shared')

from stock_shared.db.database import dbConn
from stock_shared.dao.tradeShapeTrainDailyDao import TradeShapeTrainDailyDao
from stock_shared.dto.userOptionMeta import UserOptionMeta
from stock_shared.ml.shape_features import SHAPE_FEATURE_COLUMNS
from app.ext_services.kis.KisEngine import KisEngine
from app.ext_services.kis.component.KisStockService import KisService
from app.batches.services.stockService import StockService
from app.batches.services.userService import UserService

# KIS 호출 간격. shape_full_universe_scan 과 동일 값(그 스크립트가 rate limit 없이 완주함).
SLEEP_SEC = 1.5
# 지표/피처 lookback 확보용. ema60·vol_avg·shape 14봉을 다 채우려면 넉넉해야 한다.
MIN_DAYS = 250
# 조회 하한 힌트. SAVE_FROM 보다 충분히 이전이어야 SAVE_FROM 첫날 피처가 NaN 이 아니다.
FETCH_START = '2025-06-01'

OHLCV_COLS = ('open', 'high', 'low', 'close', 'volume')

# ── 일별 적재와 동일한 유니버스 필터 ────────────────────────────────────────
#   StockBuyCheckJob 은 이 두 필터를 **학습셋 적재(_build_train_row)보다 앞단**에서
#   적용하고 미달 종목은 continue 로 건너뛴다(StockBuyCheckJob.py 406~416행).
#   그래서 일별로 쌓이는 학습셋은 '전종목'이 아니라 '거래량·가격 통과분'이다
#   (2026-10-01 실측: 2,756종목 중 320행 = 11.6%, 적재분 MIN(volume)=500,281).
#
#   백필이 이 필터를 적용하지 않으면 백필분(전종목)과 일별분(통과분)의 분포가
#   어긋난다. 라이브 추론(shape_score)도 같은 루프 안에서 통과분에만 계산되므로
#   **추론 대상 = 통과분**이고, 학습셋도 통과분으로 맞추는 게 분포 일치상 맞다.
#
#   적용 단위가 다르다는 점에 주의: 라이브는 '마지막 봉' 하나로 종목 전체를 넣거나
#   빼지만, 백필은 종목당 수십 행을 저장하므로 **봉마다 그 봉의 close/volume 으로**
#   판정한다. 그게 "그 날 라이브였다면 포함됐는가"를 날짜별로 재현하는 방식이다.
PENNY_PRICE_MIN = 1000      # StockBuyCheckJob.COMPOSITE_PENNY_PRICE_MIN 과 동일


def _passes_universe(close, volume, vol_limit: float, min_close: float) -> bool:
    """그 봉이 일별 적재 유니버스에 들었는지. 라이브와 **같은 부등호**를 쓴다.

    라이브: `if last_close < MIN: continue` / `if last_volume < vol_limit: continue`
    결측(None/NaN)은 판정 불가이므로 제외한다 — 라이브도 그 종목을 처리하지 못한다.
    """
    if close is None or volume is None:
        return False
    return not (close < min_close or volume < vol_limit)


def _build_rows(code: str, data: pd.DataFrame, save_from: str,
                vol_limit: float, min_close: float) -> tuple[list[dict], int]:
    """지표 계산이 끝난 DataFrame → (upsert 행 리스트, 유니버스 미달로 제외한 봉수).

    **fillna 하지 않는다.** 결측은 None 으로 내려보내 DB 에 NULL 로 들어가야 한다
    (16_shape_train_daily_ddl.sql 설계 포인트 1). 0 으로 채우면 "lookback 부족"이
    "관측값 0"으로 학습되고, ShapeTrainJob 이 완전행을 골라내는 것도 불가능해진다.

    피처는 **필터 적용 전 전체 시계열**로 계산한다. 거래량 미달인 날이 중간에 끼어도
    그 날 봉은 lookback 에 그대로 쓰여야 한다 — 저장만 건너뛸 뿐 계산에서 빼지 않는다.
    (여기서 걸러내면 14봉 윈도우에 구멍이 생겨 라이브와 다른 피처가 나온다)
    """
    df = data.copy()
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df[df['datetime'] >= pd.Timestamp(save_from)]
    if df.empty:
        return [], 0

    df = df.replace([np.inf, -np.inf], np.nan)

    rows = []
    filtered = 0
    for rec in df.to_dict(orient='records'):
        dt = rec.get('datetime')
        if dt is None or pd.isna(dt):
            continue

        def _v(col):
            v = rec.get(col)
            if v is None or pd.isna(v):
                return None
            return float(v)

        # 유니버스 필터는 저장 직전에 그 봉 자신의 close/volume 으로 판정한다.
        if not _passes_universe(_v('close'), _v('volume'), vol_limit, min_close):
            filtered += 1
            continue

        row = {'coin': code, 'datetime': str(pd.Timestamp(dt).date())}
        for c in SHAPE_FEATURE_COLUMNS:
            row[c] = _v(c)
        row['shape_ret_1d_today'] = _v('shape_ret_1d_today')
        for c in OHLCV_COLS:
            row[c] = _v(c)
        # 소급 재현 불가한 평가용 컬럼(상단 docstring 참고). 학습 입력 아님.
        row['shape_proba_at_scan'] = None
        row['composite_eligible'] = None
        row['action_type'] = None
        rows.append(row)
    return rows, filtered


def _already_loaded(session, save_from: str) -> set:
    """이미 적재된 종목코드 집합(--resume 용).

    주의: "1행이라도 있으면 완료"로 본다. 중단이 종목 단위로 일어나고(적재는 종목당
    1트랜잭션) 종목 내부는 통째로 upsert 되므로 부분 적재된 종목은 생기지 않는다.
    """
    rows = session.execute(
        text("SELECT DISTINCT coin FROM trade_shape_train_daily WHERE datetime >= :s"),
        {'s': save_from},
    ).all()
    return {r[0] for r in rows}


def main():
    ap = argparse.ArgumentParser(description='trade_shape_train_daily 과거 백필')
    ap.add_argument('--save-from', default='2026-06-01',
                    help='이 날짜 이후 일봉만 저장(기본 2026-06-01)')
    ap.add_argument('--limit', type=int, default=None, help='대상 종목수 제한(점검용)')
    ap.add_argument('--resume', action='store_true',
                    help='이미 적재된 종목은 건너뜀(중단 후 재실행)')
    ap.add_argument('--dry-run', action='store_true',
                    help='DB 에 쓰지 않고 계산 결과만 출력')
    ap.add_argument('--vol-limit', type=float, default=None,
                    help='거래량 하한. 기본은 운영과 동일하게 user_options 에서 읽음')
    ap.add_argument('--min-close', type=float, default=PENNY_PRICE_MIN,
                    help=f'종가 하한(기본 {PENNY_PRICE_MIN})')
    args = ap.parse_args()

    session = dbConn.get_session()
    train_dao = TradeShapeTrainDailyDao()

    # 거래량 하한은 **운영과 같은 경로**로 읽는다 — StockBuyCheckJob 도
    # UserService().get_user_options(session)(기본 user_id=1)로 vol_limit 을 얻는다.
    # 상수로 박아두면 운영에서 값을 바꿨을 때 백필분과 일별분이 조용히 갈린다.
    if args.vol_limit is not None:
        vol_limit = args.vol_limit
        vol_src = 'CLI'
    else:
        vol_limit = float(UserService().get_user_options(session).vol_limit or 0)
        vol_src = 'user_options'
    if vol_limit <= 0:
        print(f"[경고] vol_limit={vol_limit} (출처={vol_src}) → 거래량 필터가 사실상 비활성이다. "
              f"일별 적재분과 분포가 어긋날 수 있으니 값을 확인하라.", flush=True)

    stock_service = StockService()
    targets = stock_service.get_stock_master_list(session, 'batches')
    if args.limit:
        targets = targets[:args.limit]

    skip_codes = _already_loaded(session, args.save_from) if args.resume else set()
    if skip_codes:
        print(f"[resume] 이미 적재된 {len(skip_codes)}종목 건너뜀", flush=True)

    print(f"[대상] {len(targets)}종목 / 저장시작 {args.save_from} / "
          f"조회하한 {FETCH_START} / dry_run={args.dry_run}", flush=True)
    print(f"[유니버스 필터] 거래량 >= {vol_limit:,.0f}(출처={vol_src}) · "
          f"종가 >= {args.min_close:,.0f} — 일별 적재(StockBuyCheckJob)와 동일 기준",
          flush=True)

    kis_service = KisService()
    kis_engine = KisEngine()
    end_date = datetime.now().strftime('%Y-%m-%d')

    # compute_indicator_df 가 user_info 를 요구하지만 shape/ind/obv 피처 계산에는
    # 영향이 없다(게이트 판정용 값들). shape_full_universe_scan 과 동일 더미를 쓴다.
    dummy_ui = UserOptionMeta()
    dummy_ui.vol_limit = 0
    dummy_ui.vol_surge = 3.0
    dummy_ui.delay_date = 5
    dummy_ui.macd_recent_day = 20
    dummy_ui.bb_over_recent_day = 7

    ok = fail = skip = total_rows = total_filtered = 0
    t0 = time.time()

    for idx, stock in enumerate(targets):
        code = stock.get('stock_code')
        name = stock.get('stock_name') or code
        if code in skip_codes:
            skip += 1
            continue
        try:
            time.sleep(SLEEP_SEC)
            ohlcv = kis_engine.get_daily_ohlcv(code, FETCH_START, end_date,
                                               min_days=MIN_DAYS)
            if ohlcv is None or len(ohlcv) < 2:
                skip += 1
                continue

            data = kis_service.compute_indicator_df(ohlcv, user_info=dummy_ui)
            rows, filtered = _build_rows(code, data, args.save_from,
                                         vol_limit, args.min_close)
            total_filtered += filtered
            if not rows:
                # 저장할 봉이 하나도 없다 — 유니버스 미달(거래량·가격)이 대부분이다.
                skip += 1
                continue

            if args.dry_run:
                complete = sum(
                    1 for r in rows
                    if all(r[c] is not None for c in SHAPE_FEATURE_COLUMNS)
                )
                print(f"[dry-run][{idx+1}/{len(targets)}] {name}({code}) "
                      f"{len(rows)}행 (완전행 {complete} · 유니버스미달 {filtered}) "
                      f"{rows[0]['datetime']}~{rows[-1]['datetime']}", flush=True)
                ok += 1
                total_rows += len(rows)
                continue

            train_dao.upsert_daily_bulk(session, rows)
            session.commit()

            ok += 1
            total_rows += len(rows)
            elapsed = time.time() - t0
            eta_min = (elapsed / (idx + 1)) * (len(targets) - idx - 1) / 60
            print(f"[{idx+1}/{len(targets)}] {name}({code}) {len(rows)}행 적재 "
                  f"(누적 {total_rows}행, 경과 {elapsed/60:.1f}분, "
                  f"예상잔여 {eta_min:.1f}분)", flush=True)

        except Exception as e:  # noqa: BLE001 — 한 종목 실패가 전체를 멈추면 안 된다
            session.rollback()
            fail += 1
            print(f"[{idx+1}/{len(targets)}] {name}({code}) 실패: {e}", flush=True)
            continue

    kept_pct = (total_rows / (total_rows + total_filtered) * 100) if (total_rows + total_filtered) else 0
    print(f"\n[완료] 성공 {ok} / 스킵 {skip} / 실패 {fail} / 총 {total_rows}행 "
          f"(소요 {(time.time()-t0)/60:.1f}분)", flush=True)
    print(f"[유니버스] 저장 {total_rows}행 / 미달 제외 {total_filtered}행 "
          f"→ 통과율 {kept_pct:.1f}% (일별 적재 실측 11.6% 와 비슷해야 정상)", flush=True)
    if not args.dry_run and ok:
        print(f"\n다음 단계 — 라벨 확정(이 스크립트는 net_edge_fwd 를 채우지 않는다):\n"
              f"  POST /api/v1/jobs/once/SHAPE_LABEL_JOB\n"
              f'  {{"since": "{args.save_from}", "lookback_days": 9999}}', flush=True)


if __name__ == '__main__':
    main()
