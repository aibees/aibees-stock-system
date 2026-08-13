"""M3 30분봉을 trade_candle_30m 에 적재하는 배치.

대상
    M3 종목 고정 2개. KODEX 코스피100(237350) / KODEX 인버스(114800).
    M3 는 이 둘을 정·역으로 교대 매매하므로 항상 양쪽 봉이 다 필요하다.

두 가지 모드
    mode='backfill'  (기본, 1회성)
        FHKST03010230(주식일별분봉조회)로 과거 N영업일 1분봉을 긁어 30분 집계.
        종목당 하루 4콜 × 30일 = 120콜. 2종목이면 240콜. 한 번만 돌린다.

    mode='today'     (장중 30분마다)
        pykis day_chart(period=1)로 당일 1분봉 전량 → 30분 집계 → 당일분 통째 UPSERT.
        1콜/종목. 증분 커서를 관리하지 않고 매번 덮어쓰는 쪽이 단순하고 안전하다
        (PK(coin,datetime) 라 중복이 쌓이지 않는다).

왜 30일인가
    정규장 09:00~15:30 = 390분 → 30분봉 13개/일.
    지표 계산에 250봉이 필요하므로 250/13 ≈ 19.3영업일.
    20일(260봉)은 공휴일/임시휴장 하나만 껴도 미달이라 30일(≈390봉)로 잡는다.

진행 중인 봉
    확정봉만 적재한다(drop_partial=True). 09:30 실행 시 09:00봉까지만 들어간다.
    미확정 봉을 넣으면 다음 실행에서 값이 바뀌어 시그널이 뒤집힌다(repainting).

지표
    적재 전 KisService.compute_indicator_df 를 태워 일봉과 동일한 지표 컬럼을 채운다.
    → 조회측(M3 executor)이 지표를 다시 계산할 필요가 없다.

수동 실행
    POST /api/v1/jobs/once/STOCK_CANDLE_30M_BACKFILL_JOB
      {"mode": "backfill", "days": 30}          과거 30영업일 백필
      {"mode": "today"}                          당일분만 갱신
      {"stock_codes": ["237350"]}                종목 한정
"""
import time
from datetime import date, datetime, timedelta

import pandas as pd

from app.batches.jobs.job import Job
from app.batches.services.userService import UserService
from app.ext_services.kis.KisEngine import KisEngine
from app.ext_services.kis.component.KisStockService import KisService
from stock_shared.dao.tradeCandle30mDao import TradeCandle30mDao
from stock_shared.dto.userOptionMeta import UserOptionMeta


class TradeCandle30mBackfillJob(Job):
    # M3 고정 종목
    M3_CODES = ["237350", "114800"]

    # 목표 봉 수. 지표(ema120 등)가 앞구간에서 NaN 이 되지 않는 하한.
    TARGET_BARS = 250

    # 백필 기본 영업일 수. 13봉/일 × 30일 ≈ 390봉 (250 대비 55% 여유)
    DEFAULT_DAYS = 30

    # 하루 1분봉을 긁는 데 4콜이 나간다. 일자 간 간격으로 유량제한을 피한다.
    SLEEP_SEC = 0.5

    def __init__(self):
        super().__init__()
        self.job_name = 'TradeCandle30mBackfillJob'
        self.userServiceImpl = UserService()
        self.candle30mDaoImpl = TradeCandle30mDao()

    def get_name(self):
        return self.job_name

    # ------------------------------------------------------------------
    def run_batch(self, **kwargs):
        mode = kwargs.get('mode', 'backfill')
        codes = kwargs.get('stock_codes') or self.M3_CODES
        days = int(kwargs.get('days', self.DEFAULT_DAYS))

        engine = KisEngine()
        kis_service = KisService()
        meta: UserOptionMeta = self.userServiceImpl.get_user_options(self.session)

        total_rows = 0
        details = []

        for code in codes:
            try:
                if mode == 'today':
                    rows = self._run_today(engine, kis_service, meta, code)
                else:
                    rows = self._run_backfill(engine, kis_service, meta, code, days)
                total_rows += rows
                cnt = self.candle30mDaoImpl.count_by_coin(self.session, code)
                flag = 'OK' if cnt >= self.TARGET_BARS else f'부족({cnt})'
                details.append(f'{code}:{rows}행/누적{cnt}봉 {flag}')
                print(f'[{code}] {rows}행 적재 · 누적 {cnt}봉 · {flag}', flush=True)
            except Exception as e:  # noqa: BLE001
                self.session.rollback()
                print(f'[{code}] 실패: {type(e).__name__}: {e}', flush=True)
                details.append(f'{code}:실패')

        desc = f'mode={mode} · ' + ' / '.join(details)
        print(f'[완료] {desc}', flush=True)
        return {'status': 'success', 'batch_cnt': total_rows, 'desc': desc}

    # ------------------------------------------------------------------
    # backfill — 과거 N영업일
    # ------------------------------------------------------------------
    def _run_backfill(self, engine: KisEngine, kis_service: KisService,
                      meta: UserOptionMeta, code: str, days: int) -> int:
        today = date.today()
        frames = []
        collected = checked = 0
        d = today

        # 영업일 판정은 달력이 아니라 "데이터가 나오는가"로 한다.
        # 공휴일 캘린더를 따로 들고 있지 않고, 휴장일은 빈 응답으로 구분된다.
        # checked 상한은 무한루프 방지용(주말 제외 후 days*2).
        while collected < days and checked < days * 3:
            if d.weekday() < 5:                       # 주말은 호출조차 하지 않는다
                ymd = d.strftime('%Y%m%d')
                is_today = (d == today)
                df = engine.get_30m_ohlcv(code, ymd, is_today=is_today,
                                          drop_partial=True)
                checked += 1
                if not df.empty:
                    frames.append(df)
                    collected += 1
                    print(f'  [{code}] {ymd}: 30m {len(df)}봉 '
                          f'({collected}/{days}일)', flush=True)
                time.sleep(self.SLEEP_SEC)
            d -= timedelta(days=1)

        if not frames:
            print(f'  [{code}] 수집된 봉 없음 → skip', flush=True)
            return 0

        # frames 는 최신일부터 쌓였다. 시간 오름차순으로 정렬해야 지표가 맞는다.
        ohlcv = (pd.concat(frames, ignore_index=True)
                 .drop_duplicates(subset=['datetime'], keep='last')
                 .sort_values('datetime')
                 .reset_index(drop=True))

        if len(ohlcv) < self.TARGET_BARS:
            print(f'  [{code}] ⚠ {len(ohlcv)}봉 — 목표 {self.TARGET_BARS} 미달. '
                  f'days 를 늘려 재실행 필요.', flush=True)

        return self._compute_and_save(kis_service, meta, code, ohlcv)

    # ------------------------------------------------------------------
    # today — 당일분 갱신
    # ------------------------------------------------------------------
    def _run_today(self, engine: KisEngine, kis_service: KisService,
                   meta: UserOptionMeta, code: str) -> int:
        ymd = date.today().strftime('%Y%m%d')
        today_df = engine.get_30m_ohlcv(code, ymd, is_today=True, drop_partial=True)
        if today_df.empty:
            print(f'  [{code}] 당일 확정봉 없음 (장 시작 전이거나 첫 봉 미완성)', flush=True)
            return 0

        # 지표는 과거 구간이 있어야 계산된다. DB 에서 직전 봉들을 끌어와 이어붙인다.
        prior = self.candle30mDaoImpl.select_latest(
            self.session, code, limit=self.TARGET_BARS + 50)
        prior_rows = [
            {'datetime': p['datetime'],
             'open': float(p['open']), 'high': float(p['high']),
             'low': float(p['low']), 'close': float(p['close']),
             'volume': float(p['volume'])}
            for p in prior
        ]

        ohlcv = (pd.concat([pd.DataFrame(prior_rows), today_df], ignore_index=True)
                 .drop_duplicates(subset=['datetime'], keep='last')  # 당일분 우선
                 .sort_values('datetime')
                 .reset_index(drop=True))

        if len(ohlcv) < self.TARGET_BARS:
            print(f'  [{code}] ⚠ 이력 {len(ohlcv)}봉 — 백필이 선행되어야 지표가 유효하다.',
                  flush=True)

        # 지표는 전 구간으로 계산하되, 저장은 당일분만 갱신한다.
        # (과거 봉은 이미 확정 저장되어 있고 값이 바뀌지 않는다)
        computed = kis_service.compute_indicator_df(ohlcv, user_info=meta)
        computed.fillna(0.0, inplace=True)

        ymd_dash = date.today().strftime('%Y-%m-%d')
        records = [r for r in computed.to_dict(orient='records')
                   if str(r.get('datetime', '')).startswith(ymd_dash)]

        rows = self.candle30mDaoImpl.upsert_candle_bulk(self.session, code, records)
        self.session.commit()
        return rows

    # ------------------------------------------------------------------
    def _compute_and_save(self, kis_service: KisService, meta: UserOptionMeta,
                          code: str, ohlcv: pd.DataFrame) -> int:
        computed = kis_service.compute_indicator_df(ohlcv, user_info=meta)
        computed.fillna(0.0, inplace=True)
        records = computed.to_dict(orient='records')
        rows = self.candle30mDaoImpl.upsert_candle_bulk(self.session, code, records)
        self.session.commit()
        return rows
