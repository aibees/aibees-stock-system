"""최근 매수추천 종목의 차트(OHLCV + 지표)를 trade_candle_data 에 적재하는 배치.

목적
    화면(차트·백테스트) 테스트용 데이터 확보.
    매수추천 배치(StockBuyCheckJob)는 판정만 하고 compute_indicator_df 결과를 버린다.
    그래서 추천 이력이 있는 종목이라도 차트를 그리려면 KIS 를 다시 조회해야 했다.
    이 배치가 그 공백을 주기적으로 메운다.

대상
    trade_buy_target_stock 에서 **최근 N일(기본 60일) 안에 한 번이라도 추천된 종목**
    (중복 제거). 2026-08-07 기준 213종목.

적재
    종목별 일봉 → KisService.compute_indicator_df → trade_candle_data UPSERT.
    PK(coin, datetime) 기준이라 매일 돌려도 중복이 쌓이지 않고 최신값으로 덮인다.

실행
    매일 21:00 (KST) · mon-fri.
    매수추천 배치가 20:00 이므로, 그날 새로 추천된 종목까지 포함된다.

수동 실행
    POST /api/v1/jobs/once/STOCK_CANDLE_BACKFILL_JOB
    body 로 파라미터 조정 가능:
      {"days": 90}                     최근 90일 추천 종목
      {"end_date": "2026-08-07"}       기준일 지정
      {"stock_codes": ["035420"]}      특정 종목만 (대상 조회 건너뜀)
"""
import time

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

from app.batches.jobs.job import Job
from app.batches.services.userService import UserService
from app.config.database import dbConn
from app.ext_services.kis.KisEngine import KisEngine
from app.ext_services.kis.keyLoader import list_kis_user_ids
from app.ext_services.kis.component.KisStockService import KisService
from stock_shared.dao.tradeBuyTargetStockDao import TradeBuyTargetStockDao
from stock_shared.dao.tradeCandleDataDao import TradeCandleDataDao
from stock_shared.dto.userOptionMeta import UserOptionMeta


class TradeCandleBackfillJob(Job):
    # 지표 계산에 필요한 일봉 수. get_daily_ohlcv 가 이 거래일수를 보장한다.
    #   ema120·bb_width_avg 같은 장기 지표가 앞구간에서 NaN 이 되지 않도록 넉넉히 잡는다.
    MIN_DAYS = 250

    # KIS rate limit 회피용 종목 간 간격(초). StockBuyCheckJob 과 동일 기조.
    SLEEP_SEC = 1.5

    def __init__(self):
        super().__init__()
        self.job_name = 'TradeCandleBackfillJob'
        self.userServiceImpl = UserService()
        self.buyTargetDaoImpl = TradeBuyTargetStockDao()
        self.candleDaoImpl = TradeCandleDataDao()

    def get_name(self):
        return self.job_name

    @staticmethod
    def _split_even(items: list, n: int) -> list:
        """items 를 최대 n 개의 연속 청크로 분할."""
        if n <= 1:
            return [items]
        size = (len(items) + n - 1) // n
        return [items[i:i + size] for i in range(0, len(items), size)] or [[]]

    ####################################################
    # 배치 시작
    ####################################################
    def run_batch(self, **kwargs):
        today = date.today()

        end_date = kwargs.get('end_date', today.strftime('%Y-%m-%d'))
        days = int(kwargs.get('days', 60))
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        from_ymd = (end_dt - timedelta(days=days)).strftime('%Y%m%d')

        # 일봉 조회 하한. get_daily_ohlcv(min_days=250) 이 부족분을 알아서 더 당겨오므로
        # 여기서는 힌트만 준다.
        start_date = (end_dt - timedelta(days=self.MIN_DAYS * 2)).strftime('%Y-%m-%d')

        # ── 대상 종목 ──────────────────────────────────────────────
        codes = kwargs.get('stock_codes')
        if codes:
            targets = [{'stock_code': c, 'stock_name': c} for c in codes]
            print(f'[대상] 지정 종목 {len(targets)}건', flush=True)
        else:
            targets = self.buyTargetDaoImpl.select_target_codes_since(self.session, from_ymd)
            print(f'[대상] {from_ymd} 이후 추천 종목 {len(targets)}건 '
                  f'(기준일 {end_date} · 최근 {days}일)', flush=True)

        if not targets:
            return {'status': 'SUCCESS', 'batch_cnt': 0,
                    'desc': f'{from_ymd} 이후 추천 종목이 없습니다.'}

        stock_option_meta: UserOptionMeta = self.userServiceImpl.get_user_options(self.session)

        # ── 유저별 KIS 엔진(독립 appkey = 독립 rate limit)으로 병렬 분할 ──
        try:
            uids = list_kis_user_ids()
        except Exception as e:  # noqa: BLE001
            print(f'[run_batch] KIS 유저 조회 실패 → 파일 단일 엔진 fallback: {e}', flush=True)
            uids = []

        engines = []
        for uid in uids:
            try:
                engines.append((uid, KisEngine(user_id=uid)))
            except Exception as e:  # noqa: BLE001
                print(f'[run_batch] user_id={uid} 엔진 생성 실패 → 제외: {e}', flush=True)
        if not engines:
            engines = [(None, KisEngine())]

        n = len(engines)
        chunks = self._split_even(targets, n)
        print(f'병렬 분할: 엔진 {n}개 → 청크 {[len(c) for c in chunks]}', flush=True)

        total_codes = total_rows = total_fail = 0
        with ThreadPoolExecutor(max_workers=n) as ex:
            futures = []
            for (uid, engine), chunk in zip(engines, chunks):
                if not chunk:
                    continue
                futures.append(ex.submit(
                    self._process_chunk, uid, engine, chunk,
                    stock_option_meta, start_date, end_date,
                ))
            for f in futures:
                try:
                    c, r, fa = f.result()
                    total_codes += c
                    total_rows += r
                    total_fail += fa
                except Exception as e:  # noqa: BLE001
                    print(f'[run_batch] 워커 실패: {e}', flush=True)

        desc = (f'{len(targets)}종목 중 {total_codes}종목 · {total_rows}행 적재'
                + (f' (실패 {total_fail}종목)' if total_fail else ''))
        print(f'[완료] {desc}', flush=True)

        return {
            'status': 'SUCCESS',
            'batch_cnt': total_codes,
            'desc': desc,
        }

    ####################################################
    # 청크 워커 (스레드)
    #
    #  StockBuyCheckJob 과 달리 **스레드가 직접 DB 에 저장**한다.
    #  213종목 × 250봉 ≈ 5만 행을 메인 스레드로 모아 두면 메모리를 크게 먹는다.
    #  종목 단위로 바로 흘려보내면 상주 메모리가 종목 1개분으로 유지된다.
    #
    #  dbConn.get_session() 은 scoped_session 이라 스레드마다 독립 세션을 준다.
    #  다 쓰면 반드시 remove() 로 반납해야 커넥션이 새지 않는다.
    ####################################################
    def _process_chunk(self, uid, engine: KisEngine, chunk: list,
                       stock_option_meta: UserOptionMeta,
                       start_date: str, end_date: str):
        tag = f'u{uid}' if uid is not None else 'file'
        kis_service = KisService()          # 스레드 로컬
        session = dbConn.get_session()      # 스레드 로컬 세션

        saved_codes = saved_rows = failed = 0
        idx = 0

        try:
            while idx < len(chunk):
                stock = chunk[idx]
                code = stock.get('stock_code')
                name = stock.get('stock_name') or code

                try:
                    time.sleep(self.SLEEP_SEC)

                    ohlcv = engine.get_daily_ohlcv(code, start_date, end_date,
                                                   min_days=self.MIN_DAYS)
                    if ohlcv is None or len(ohlcv) < 2:
                        print(f'[{tag}][{idx}] {name}({code}) 데이터 없음 → skip', flush=True)
                        idx += 1
                        continue

                    computed = kis_service.compute_indicator_df(
                        ohlcv, user_info=stock_option_meta)
                    computed.fillna(0.0, inplace=True)
                    records = computed.to_dict(orient='records')

                    rows = self.candleDaoImpl.upsert_candle_data_kis_bulk(
                        session, code, records)
                    session.commit()        # 종목 단위 커밋 — 한 종목 실패가 전체를 되돌리지 않는다

                    saved_codes += 1
                    saved_rows += rows
                    print(f'[{tag}][{idx}] {name}({code}) {rows}행 적재', flush=True)
                    idx += 1

                except ConnectionError:
                    print(f'[{tag}][{idx}] 네트워크 오류 → 3초 후 재시도', flush=True)
                    session.rollback()
                    time.sleep(3)
                    continue                # idx 유지 → 동일 종목 재시도

                except Exception as e:  # noqa: BLE001
                    session.rollback()
                    msg = str(e)
                    if 'API 호출 횟수를 초과' in msg:
                        print(f'[{tag}][{idx}] rate limit → 재시도', flush=True)
                        time.sleep(1)
                        continue            # idx 유지 → 재시도
                    print(f'[{tag}][{idx}] {name}({code}) 실패: {msg}', flush=True)
                    failed += 1
                    idx += 1
                    continue
        finally:
            # scoped_session 반납. 빠뜨리면 스레드 종료 후에도 커넥션이 남는다.
            session.remove()

        print(f'[{tag}] 청크 완료: {saved_codes}종목 · {saved_rows}행'
              + (f' · 실패 {failed}' if failed else ''), flush=True)
        return saved_codes, saved_rows, failed
