"""shape 재학습 학습셋의 라벨(net_edge_fwd)을 확정하는 배치.

목적
    trade_shape_train_daily 에 StockBuyCheckJob 이 append 한 일별 피처 행 중,
    **향후 5거래일(LABEL_FORWARD_BARS)이 이미 쌓인** 행의 net_edge_fwd 를 계산해
    UPDATE 한다. 라벨 정의는 stock_shared.ml.shape_label 단일 출처를 쓴다.

API 호출 0건
    라벨 계산에 필요한 close/high/low 가 이미 같은 테이블에 적재돼 있다.
    KIS 재조회 없이 테이블 안에서 자기완결적으로 계산한다.

엠바고
    T일 피처는 T+5 거래일이 쌓인 뒤에야 라벨이 확정된다. 이걸 어기면
    look-ahead 누수로 백테스트가 실제보다 좋게 나온다.

적재 공백 방어
    "그 종목의 다음 5개 저장봉"으로 계산하므로, 적재가 며칠 빠지면 창이 실제
    5거래일보다 훨씬 먼 미래가 된다. base 와 5번째 봉의 캘린더 간격이
    LABEL_MAX_SPAN_DAYS 를 넘으면 라벨을 채우지 않고 남겨둔다(다음 실행에서도
    동일 판정 → 영구 미확정. 공백을 메우려면 별도 백필이 필요하다는 신호).

실행
    매 평일 21:40 (KST). StockBuyCheckJob(20:00) 적재 이후.
    batch_job_master 등록은 sql/17_shape_train_job_register.sql 참고.

수동 실행
    POST /api/v1/jobs/once/SHAPE_LABEL_JOB
    body:
      {"since": "2026-09-01"}   이 날짜 이후 미확정 행만 대상(기본: 최근 LOOKBACK_DAYS)
      {"lookback_days": 120}
"""
from datetime import datetime, timedelta

from app.batches.jobs.job import Job
from stock_shared.dao.tradeShapeTrainDailyDao import TradeShapeTrainDailyDao
from stock_shared.ml.shape_label import (
    LABEL_FORWARD_BARS,
    LABEL_MAX_SPAN_DAYS,
    compute_net_edge_fwd,
)


class ShapeLabelJob(Job):
    # 미확정 행 탐색 범위(캘린더 일). 5봉 엠바고 + 연휴 + 여유를 감안한 기본값.
    #   너무 좁으면 적재 공백 뒤의 행이 영구 미확정으로 남고,
    #   너무 넓으면 매일 같은 과거 행을 재계산한다(비용은 작지만 무의미).
    LOOKBACK_DAYS = 60

    def __init__(self):
        super().__init__()
        self.job_name = 'ShapeLabelJob'
        self.trainDaoImpl = TradeShapeTrainDailyDao()

    def get_name(self):
        return self.job_name

    def run_batch(self, **kwargs):
        lookback_days = int(kwargs.get('lookback_days', self.LOOKBACK_DAYS))
        since = kwargs.get('since') or \
            (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

        coins = self.trainDaoImpl.select_unlabeled_coins(self.session, since)
        print(f"[ShapeLabelJob] 라벨 미확정 종목 {len(coins)}개 (since={since})", flush=True)
        if not coins:
            summary = self.trainDaoImpl.count_summary(self.session)
            return {
                'status': 'SUCCESS', 'batch_cnt': 0,
                'desc': f"확정할 라벨이 없습니다. (적재 {summary['total']}행 / "
                        f"라벨 {summary['labeled']}행)"
            }

        rows = self.trainDaoImpl.select_series(self.session, coins, since)
        print(f"[ShapeLabelJob] 계산 대상 {len(rows)}행 조회", flush=True)

        # 종목별로 묶어 순서대로 라벨 계산
        by_coin: dict[str, list[dict]] = {}
        for r in rows:
            by_coin.setdefault(r['coin'], []).append(r)

        updates = []
        skipped_span = 0
        for coin, series in by_coin.items():
            if len(series) <= LABEL_FORWARD_BARS:
                continue
            labels = compute_net_edge_fwd(
                [r['close'] for r in series],
                [r['high'] for r in series],
                [r['low'] for r in series],
            )
            for i, r in enumerate(series):
                if r['net_edge_fwd'] is not None:      # 이미 확정된 행은 건너뜀
                    continue
                v = labels[i]
                if v != v:                              # NaN (향후 봉 부족/결측)
                    continue
                # 적재 공백 방어: base ~ 5번째 봉의 캘린더 간격 확인
                last = series[i + LABEL_FORWARD_BARS]
                span = (datetime.strptime(last['datetime'], '%Y-%m-%d')
                        - datetime.strptime(r['datetime'], '%Y-%m-%d')).days
                if span > LABEL_MAX_SPAN_DAYS:
                    skipped_span += 1
                    continue
                updates.append({'coin': coin, 'datetime': r['datetime'],
                                'net_edge_fwd': round(float(v), 4)})

        n = self.trainDaoImpl.update_labels_bulk(self.session, updates)
        self.session.commit()

        summary = self.trainDaoImpl.count_summary(self.session)
        desc = (f"라벨 {n}건 확정 (적재공백으로 스킵 {skipped_span}건). "
                f"누적 적재 {summary['total']}행 / 라벨 {summary['labeled']}행 "
                f"({summary['min_dt']}~{summary['max_dt']})")
        print(f"[ShapeLabelJob] {desc}", flush=True)
        return {'status': 'SUCCESS', 'batch_cnt': n, 'desc': desc}
