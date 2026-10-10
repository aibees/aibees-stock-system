"""
StockInvestorJob — 종목별 투자자(개인/외국인/기관) 순매수 적재 (평일 07:10).

종목 화면의 '전일 수급' 표시용. KIS 주식현재가 투자자(FHKST01010900)를 종목당 1회 호출해
응답(최근 ~30영업일) 중 최근 keep_days 영업일을 stock_investor_daily 에 upsert 한다.
최근 며칠을 같이 덮어쓰므로 하루 배치를 놓쳐도 다음 날 자동으로 메워진다.

  - 대상: master_stock 중 ETF(group_code='EF') 제외 — 07:00 STOCK_CODE_MASTER_JOB 이 먼저 갱신해 둔다.
  - 병렬: StockBuyCheckJob 과 같이 KIS 유저(앱키)별로 나눠 스레드 병렬. 스레드는 조회만(무 DB).
          rate limit / 초당 건수 초과(EGW00201) 재시도는 pykis 가 처리한다.
  - 보관: 90일 지난 행은 삭제.

수동 실행 인자(kwargs): keep_days(기본 5), limit(테스트용 종목 수 제한)
"""
import time
from concurrent.futures import ThreadPoolExecutor

from app.batches.jobs.job import Job
from app.ext_services.kis.KisEngine import KisEngine
from app.ext_services.kis.keyLoader import list_kis_user_ids
from stock_shared.dao.masterStockDao import MasterStockDao
from stock_shared.dao.stockInvestorDailyDao import StockInvestorDailyDao

EXCLUDE_GROUPS = {'EF'}      # ETF — 화면 대상 아님(호출 수 ~1,200 절감)
RETENTION_DAYS = 90
CALL_INTERVAL_SEC = 0.15     # 같은 앱키를 쓰는 trade worker 몫의 여유


class StockInvestorJob(Job):
    def __init__(self):
        super().__init__()
        self.job_name = "StockInvestorJob"
        self.masterStockDaoImpl = MasterStockDao()
        self.investorDaoImpl = StockInvestorDailyDao()

    def get_name(self):
        return self.job_name

    @staticmethod
    def _split_even(items: list, n: int) -> list:
        if n <= 1:
            return [items]
        size = (len(items) + n - 1) // n  # ceil
        return [items[i:i + size] for i in range(0, len(items), size)] or [[]]

    def run_batch(self, **kwargs):
        keep_days = int(kwargs.get('keep_days', 5))
        limit = kwargs.get('limit')

        codes = [s['stock_code'] for s in self.masterStockDaoImpl.select_all_stocks(self.session)
                 if s.get('group_code') not in EXCLUDE_GROUPS]
        if limit:
            codes = codes[:int(limit)]
        print(f'[StockInvestorJob] 대상 종목 {len(codes)}개, 최근 {keep_days}영업일 적재', flush=True)

        # 유저(앱키)별 엔진 — 없으면 파일 단일 엔진으로 직렬 (StockBuyCheckJob 과 동일한 방식)
        try:
            uids = list_kis_user_ids()
        except Exception as e:
            print(f"[StockInvestorJob] KIS 유저 조회 실패 → 파일 단일 엔진 fallback: {e}", flush=True)
            uids = []
        engines = []
        for uid in uids:
            try:
                engines.append((uid, KisEngine(user_id=uid)))
            except Exception as e:
                print(f"[StockInvestorJob] user_id={uid} 엔진 생성 실패 → 제외: {e}", flush=True)
        if not engines:
            engines = [(None, KisEngine())]

        chunks = self._split_even(codes, len(engines))
        rows, failed = [], 0
        with ThreadPoolExecutor(max_workers=len(engines)) as ex:
            futures = [ex.submit(self._fetch_chunk, engine, chunk, keep_days)
                       for (_, engine), chunk in zip(engines, chunks) if chunk]
            for f in futures:
                try:
                    chunk_rows, chunk_failed = f.result()
                    rows.extend(chunk_rows)
                    failed += chunk_failed
                except Exception as e:
                    print(f"[StockInvestorJob] 워커 실패: {e}", flush=True)

        saved = self.investorDaoImpl.upsert_bulk(self.session, rows)
        deleted = self.investorDaoImpl.delete_older_than(self.session, RETENTION_DAYS)
        self.session.commit()

        latest = max((r['ymd'] for r in rows), default='-')
        desc = f'투자자 순매수 {saved}행 적재(최근일 {latest}), 실패 {failed}종목, {RETENTION_DAYS}일 경과 {deleted}행 삭제'
        print(f'[StockInvestorJob] {desc}', flush=True)
        return {
            # 대부분 실패면(장애·토큰 문제) 실패로 남겨 알림이 가게 한다
            'status': 'FAIL' if codes and failed > len(codes) // 2 else 'SUCCESS',
            'desc': desc,
            'batch_cnt': saved,
        }

    @staticmethod
    def _fetch_chunk(engine: KisEngine, codes: list, keep_days: int):
        rows, failed = [], 0
        for i, code in enumerate(codes):
            time.sleep(CALL_INTERVAL_SEC)
            data = engine.get_investor_daily(code)
            if data is None:
                failed += 1
                continue
            for r in data[:keep_days]:
                rows.append({**r, 'stock_code': code})
            if (i + 1) % 500 == 0:
                print(f'[StockInvestorJob] 진행 {i + 1}/{len(codes)}', flush=True)
        return rows, failed
