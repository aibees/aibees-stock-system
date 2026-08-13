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
      {"mode": "backfill", "days": 30}              오늘부터 과거 30영업일
      {"end_date": "2026-07-31", "days": 30}        지정일부터 과거 30영업일
      {"ym": "202601"}                               2026년 1월 전체
      {"mode": "today"}                              당일분만 갱신
      {"stock_codes": ["237350"]}                    종목 한정

구간 지정 파라미터 (택 1)
    ym        'YYYYMM' / 'YYYY-MM'. 해당 **월 전체**의 평일을 수집한다.
              days 는 무시된다(월 전체가 목표).
              진행 중인 달이면 오늘까지만. 미래 달이면 대상 없음.
              → 월 단위로 끊어 백필할 때. 로그·재실행 단위가 깔끔하다.

    end_date  'YYYY-MM-DD' / 'YYYYMMDD'. 이 날(포함)부터 과거로 days 영업일.
              미지정 시 오늘. ym 이 있으면 무시된다.
              → 소급 한계에 걸려 임의 구간으로 쪼개 받을 때.

    두 모드 모두 기준일이 오늘이 아니면 과거 API(FHKST03010230)로 조회한다.
    (당일 API 는 오늘 세션만 반환하므로 과거 일자엔 의미가 없다)

구간을 나눠 받아도 지표가 깨지지 않는 이유
    _compute_and_save 가 저장 전에 DB 이력을 전부 끌어와 합친 뒤,
    **연속된 시계열** 위에서 지표를 계산한다.
    지표는 과거만 참조하므로, 뒤늦게 앞구간을 채우면 이미 저장된 뒷구간
    지표도 함께 교정된다(수집분 시작 시각 이후 전 구간 재저장).
    → ym 을 202601, 202602, ... 순서와 무관하게 돌려도 결과가 같다.
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
        end_date = self._parse_end_date(kwargs.get('end_date'))
        ym = self._parse_ym(kwargs.get('ym'))

        # 대상 일자 계획을 미리 확정한다. 종목마다 같은 구간을 돌아야
        # 두 종목의 봉 구간이 어긋나지 않는다(M3 는 정·역 비교 매매).
        plan_days, plan_target, plan_label = self._build_day_plan(days, end_date, ym)

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
                    rows = self._run_backfill(engine, kis_service, meta, code,
                                              plan_days, plan_target, plan_label)
                total_rows += rows
                cnt = self.candle30mDaoImpl.count_by_coin(self.session, code)
                flag = 'OK' if cnt >= self.TARGET_BARS else f'부족({cnt})'
                details.append(f'{code}:{rows}행/누적{cnt}봉 {flag}')
                print(f'[{code}] {rows}행 적재 · 누적 {cnt}봉 · {flag}', flush=True)
            except Exception as e:  # noqa: BLE001
                self.session.rollback()
                print(f'[{code}] 실패: {type(e).__name__}: {e}', flush=True)
                details.append(f'{code}:실패')

        head = (f'mode={mode} · ' if mode == 'today'
                else f'mode={mode} · {plan_label} · ')
        desc = head + ' / '.join(details)
        print(f'[완료] {desc}', flush=True)
        return {'status': 'SUCCESS', 'batch_cnt': total_rows, 'desc': desc}

    # ------------------------------------------------------------------
    # 파라미터 해석
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_end_date(v) -> date:
        """end_date 파라미터 해석. 'YYYY-MM-DD' / 'YYYYMMDD' / None(=오늘)."""
        if not v:
            return date.today()
        if isinstance(v, date):
            return v
        s = str(v).strip().replace('-', '')
        try:
            return datetime.strptime(s, '%Y%m%d').date()
        except ValueError:
            raise ValueError(f"end_date 형식 오류: {v!r} (YYYY-MM-DD 또는 YYYYMMDD)")

    @staticmethod
    def _parse_ym(v) -> tuple | None:
        """ym 파라미터 해석. '202601' / '2026-01' → (2026, 1). None 이면 None."""
        if not v:
            return None
        s = str(v).strip().replace('-', '')
        if len(s) != 6 or not s.isdigit():
            raise ValueError(f"ym 형식 오류: {v!r} (YYYYMM 또는 YYYY-MM)")
        y, m = int(s[:4]), int(s[4:])
        if not 1 <= m <= 12:
            raise ValueError(f"ym 월 범위 오류: {v!r}")
        return y, m

    def _build_day_plan(self, days: int, end_date: date, ym: tuple | None):
        """수집 대상 후보 일자를 **최신 → 과거** 순으로 확정한다.

        반환: (후보일자 리스트, 목표 영업일 수 | None, 사람이 읽는 라벨)

        목표 수가 None 이면 "후보 전량 수집"이다(ym 모드).
        목표 수가 있으면 데이터가 나온 날만 세어 그 수를 채우면 중단한다
        (공휴일 캘린더가 없어 휴장일은 빈 응답으로만 구분되기 때문).

        주말은 후보에서 아예 제외한다 — 호출 자체가 낭비다.
        """
        today = date.today()

        # ── ym 모드: 해당 월 전체 ──────────────────────────────────
        if ym:
            y, m = ym
            first = date(y, m, 1)
            # 다음 달 1일 - 1일 = 이번 달 말일 (12월 → 이듬해 1월로 넘어감)
            nxt = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
            last = nxt - timedelta(days=1)

            if first > today:
                print(f'  [계획] {y}-{m:02d} 은 미래 월 → 대상 없음', flush=True)
                return [], None, f'ym={y}{m:02d}(미래)'

            # 진행 중인 달이면 오늘까지만
            if last > today:
                last = today

            cands = []
            d = last
            while d >= first:
                if d.weekday() < 5:
                    cands.append(d)
                d -= timedelta(days=1)

            label = (f'ym={y}{m:02d}({first:%m/%d}~{last:%m/%d}, '
                     f'평일 {len(cands)}일)')
            print(f'  [계획] {label}', flush=True)
            return cands, None, label

        # ── end_date/days 모드: 기준일부터 과거로 ──────────────────
        # 후보는 목표의 3배까지 넉넉히 뽑고, 실제 중단은 수집 성공 수로 판단한다.
        cands = []
        d = end_date
        while len(cands) < days * 3:
            if d.weekday() < 5:
                cands.append(d)
            d -= timedelta(days=1)

        label = f'end_date={end_date:%Y-%m-%d} · days={days}'
        print(f'  [계획] {label}', flush=True)
        return cands, days, label

    # ------------------------------------------------------------------
    # backfill — 계획된 일자들을 수집
    # ------------------------------------------------------------------
    def _run_backfill(self, engine: KisEngine, kis_service: KisService,
                      meta: UserOptionMeta, code: str,
                      plan_days: list, target: int | None, label: str) -> int:
        if not plan_days:
            print(f'  [{code}] 대상 일자 없음 → skip', flush=True)
            return 0

        today = date.today()
        frames = []
        collected = 0

        print(f'  [{code}] 백필 시작: {label}', flush=True)

        for d in plan_days:
            if target is not None and collected >= target:
                break

            ymd = d.strftime('%Y%m%d')
            # 당일 API 는 오늘 세션만 반환한다. 과거 일자는 전부 과거 API.
            is_today = (d == today)
            df = engine.get_30m_ohlcv(code, ymd, is_today=is_today,
                                      drop_partial=True)
            if not df.empty:
                frames.append(df)
                collected += 1
                progress = f'{collected}/{target}일' if target else f'{collected}일'
                print(f'  [{code}] {ymd}: 30m {len(df)}봉 ({progress})', flush=True)
            time.sleep(self.SLEEP_SEC)

        if not frames:
            print(f'  [{code}] 수집된 봉 없음 → skip '
                  f'({label}, {len(plan_days)}일 조회)', flush=True)
            return 0

        # frames 는 최신일부터 쌓였다. 시간 오름차순으로 정렬해야 지표가 맞는다.
        ohlcv = (pd.concat(frames, ignore_index=True)
                 .drop_duplicates(subset=['datetime'], keep='last')
                 .sort_values('datetime')
                 .reset_index(drop=True))

        # 이 회차 수집분 기준 안내. 누적 충족 여부는 run_batch 가 DB 기준으로 찍는다.
        if len(ohlcv) < self.TARGET_BARS:
            oldest = ohlcv['datetime'].iloc[0][:10]
            print(f'  [{code}] 이번 회차 {len(ohlcv)}봉 ({collected}영업일). '
                  f'누적이 {self.TARGET_BARS}봉 미만이면 {oldest} 이전 구간을 '
                  f'추가 백필할 것 (ym 또는 end_date 로 지정).', flush=True)

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
        """수집분을 DB 이력과 합쳐 지표를 계산하고 저장한다.

        왜 DB 이력을 끌어오는가:
            ym/end_date 로 구간을 나눠 백필하면, 회차마다 그 구간만 보고
            지표가 계산된다. ema120·bb_width_avg 같은 장기 지표는 구간 앞머리가
            전부 왜곡된다(직전 구간을 못 보므로).
            → DB 에 이미 있는 봉을 전부 합쳐 **연속된 시계열** 위에서 계산한다.

        저장 범위:
            지표는 과거만 참조하므로, 이번에 새로 끼워 넣은 구간보다 **뒤쪽 봉들도**
            값이 바뀐다(예: 1월을 나중에 채우면 이미 저장된 2월 지표가 교정된다).
            그래서 '수집분 최소 datetime 이후 전 구간'을 다시 저장한다.
        """
        if ohlcv.empty:
            return 0

        first_dt = str(ohlcv['datetime'].min())

        # DB 이력 (OHLCV 만 취한다. 지표는 여기서 다시 계산한다)
        prior = self.candle30mDaoImpl.select_latest(self.session, code, limit=100000)
        prior_rows = [
            {'datetime': p['datetime'],
             'open': float(p['open']), 'high': float(p['high']),
             'low': float(p['low']), 'close': float(p['close']),
             'volume': float(p['volume'])}
            for p in prior
        ]

        if prior_rows:
            merged = pd.concat([pd.DataFrame(prior_rows), ohlcv], ignore_index=True)
        else:
            merged = ohlcv.copy()

        merged = (merged
                  .drop_duplicates(subset=['datetime'], keep='last')  # 신규 수집분 우선
                  .sort_values('datetime')
                  .reset_index(drop=True))

        computed = kis_service.compute_indicator_df(merged, user_info=meta)
        computed.fillna(0.0, inplace=True)

        # 앞구간(워밍업)은 지표가 어차피 부정확하고 이미 저장돼 있으므로 건드리지 않는다.
        records = [r for r in computed.to_dict(orient='records')
                   if str(r.get('datetime', '')) >= first_dt]

        if len(merged) > len(ohlcv):
            print(f'  [{code}] DB 이력 {len(prior_rows)}봉 + 신규 {len(ohlcv)}봉 '
                  f'→ {len(merged)}봉 위에서 지표 계산 · {len(records)}행 저장',
                  flush=True)

        rows = self.candle30mDaoImpl.upsert_candle_bulk(self.session, code, records)
        self.session.commit()
        return rows
