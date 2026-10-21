"""백테스트용 일봉 원천(수정주가)을 stock_ohlcv_daily 에 쌓는 배치.

목적
    패턴 분석·백테스트에 쓸 5년치 일봉을 DB 에 보관한다.
    trade_candle_data 는 추천 종목·지표 포함·250봉 단위라 이 용도로는 넓고 짧다.
    여기는 OHLCV + 거래대금만, 종목당 약 1,225봉 × 매수추천 대상 전 종목.

대상
    매수추천 배치와 같은 목록(StockService.get_stock_master_list('batches')).
    ST/RT/MF 정상거래 + 코스피200·인버스 ETF. 2026-10-21 기준 약 2,650종목.

처리 (한 번 실행에 두 종류를 함께 돈다)
    1) 백필: 상태가 없거나 미완료인 종목을 **최대 limit 종목**(기본 700)만 5년치 수집 → 종목 전체 교체.
       종목당 KIS 약 15콜. mon-sat 하루 한 번이면 4회(약 4일)에 전 종목이 채워진다.
    2) 증분: 백필 완료 종목은 최근 OVERLAP_DAYS 만 1콜로 다시 받는다.
       이미 저장된 날과 겹치는 종가를 비교해 하나라도 다르면 수정주가가 바뀐 것(분할·증자 등)
       → 그 종목만 5년치를 다시 받아 통째로 교체한다. 같으면 마지막 저장일 이후만 UPSERT.

buffer pool
    쓰기는 종목 단위(최대 약 1,225행)로 끊어 커밋하고, 증분은 종목당 몇 행만 건드린다.
    읽기는 증분 비교용 최근 구간뿐이라 테이블 전체를 훑는 일이 없다.

실행
    mon-sat 23:00 (KST). 매수추천(20:30)·캔들/라벨/성과(21:30~21:50) 이후.

수동 실행
    POST /api/v1/jobs/once/STOCK_OHLCV_DAILY_JOB
    body 로 파라미터 조정 가능:
      {"limit": 1000}                  이번 실행의 백필 종목 수
      {"mode": "backfill"}             백필만 (incremental = 증분만, 기본 all)
      {"years": 5}                     백필 기간(년)
      {"stock_codes": ["005930"]}      특정 종목 강제 전체 재수집 (대상 조회 건너뜀)
"""
import time

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from app.batches.jobs.job import Job
from app.batches.services.stockService import StockService
from stock_shared.db.database import dbConn
from app.ext_services.kis.KisEngine import KisEngine
from app.ext_services.kis.keyLoader import list_kis_user_ids
from stock_shared.dao.stockOhlcvDailyDao import StockOhlcvDailyDao


class StockOhlcvDailyJob(Job):
    # 백필 기간 기본값(년)과 1회 실행당 백필 종목 수 기본값.
    YEARS = 5
    LIMIT = 700

    # 증분 재조회 구간(캘린더일). 일봉 1콜 윈도우(130일) 안에 들어야 1콜로 끝난다.
    OVERLAP_DAYS = 120

    # KIS 호출 간격(초). pykis 가 appkey 별 rate limit 을 이미 걸지만, 야간이라도
    # 다른 잡과 겹칠 때를 대비해 약간 띄운다.
    CALL_GAP = 0.1
    STOCK_GAP = 0.2

    # rate limit 응답 시 같은 종목 재시도 상한.
    MAX_RETRY = 5

    def __init__(self):
        super().__init__()
        self.job_name = 'StockOhlcvDailyJob'
        self.stockServiceImpl = StockService()
        self.ohlcvDaoImpl = StockOhlcvDailyDao()

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
        years = int(kwargs.get('years', self.YEARS))
        limit = int(kwargs.get('limit', self.LIMIT))
        mode = kwargs.get('mode', 'all')
        backfill_from = today - timedelta(days=years * 365 + 7)   # 윤년·연초 휴장 여유

        # ── 대상 분류 ──────────────────────────────────────────────
        codes = kwargs.get('stock_codes')
        if codes:
            work = [('backfill', {'stock_code': c, 'stock_name': c}, None) for c in codes]
            remain = 0
            print(f'[대상] 지정 종목 {len(work)}건 강제 전체 재수집', flush=True)
        else:
            stocks = self.stockServiceImpl.get_stock_master_list(self.session, 'batches')
            states = self.ohlcvDaoImpl.select_states(self.session)

            pending = [s for s in stocks
                       if (states.get(s['stock_code']) or {}).get('backfill_done') != 'Y']
            # 한 번도 시도 안 한 종목을 먼저, 실패 이력이 있는 종목은 뒤로.
            pending.sort(key=lambda s: (s['stock_code'] in states, s['stock_code']))
            done = [s for s in stocks
                    if (states.get(s['stock_code']) or {}).get('backfill_done') == 'Y']

            work = []
            if mode in ('all', 'incremental'):
                work += [('incremental', s, states[s['stock_code']]) for s in done]
            if mode in ('all', 'backfill'):
                work += [('backfill', s, states.get(s['stock_code'])) for s in pending[:limit]]
            remain = max(len(pending) - limit, 0) if mode in ('all', 'backfill') else len(pending)
            print(f'[대상] 전체 {len(stocks)}종목 · 증분 {len(done)} · 백필 대기 {len(pending)} '
                  f'(이번 {min(len(pending), limit) if mode != "incremental" else 0}) · mode={mode}',
                  flush=True)

        if not work:
            return {'status': 'SUCCESS', 'batch_cnt': 0, 'desc': '처리할 종목이 없습니다.'}

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
        chunks = self._split_even(work, n)
        print(f'병렬 분할: 엔진 {n}개 → 청크 {[len(c) for c in chunks]}', flush=True)

        total = {'backfill': 0, 'incremental': 0, 'readjust': 0, 'rows': 0, 'failed': 0}
        with ThreadPoolExecutor(max_workers=n) as ex:
            futures = [ex.submit(self._process_chunk, uid, engine, chunk, backfill_from, today)
                       for (uid, engine), chunk in zip(engines, chunks) if chunk]
            for f in futures:
                try:
                    for k, v in f.result().items():
                        total[k] += v
                except Exception as e:  # noqa: BLE001
                    print(f'[run_batch] 워커 실패: {e}', flush=True)

        desc = (f"백필 {total['backfill']} · 증분 {total['incremental']} · "
                f"수정주가 재수집 {total['readjust']} · {total['rows']}행"
                + (f" · 실패 {total['failed']}" if total['failed'] else '')
                + (f' · 남은 백필 {remain}종목' if remain else ''))
        print(f'[완료] {desc}', flush=True)

        return {
            'status': 'SUCCESS',
            'batch_cnt': total['backfill'] + total['incremental'],
            'desc': desc,
        }

    ####################################################
    # 청크 워커 (스레드)
    #   스레드가 종목 단위로 바로 저장·커밋한다. 상주 메모리는 종목 1개분(최대 약 1,225행).
    #   dbConn.get_session() 은 scoped_session 이라 스레드마다 독립 세션 → 끝나면 remove().
    ####################################################
    def _process_chunk(self, uid, engine: KisEngine, chunk: list,
                       backfill_from: date, today: date) -> dict:
        tag = f'u{uid}' if uid is not None else 'file'
        session = dbConn.get_session()
        cnt = {'backfill': 0, 'incremental': 0, 'readjust': 0, 'rows': 0, 'failed': 0}

        idx = retry = 0
        try:
            while idx < len(chunk):
                kind, stock, state = chunk[idx]
                code = stock['stock_code']
                name = stock.get('stock_name') or code
                try:
                    time.sleep(self.STOCK_GAP)
                    if kind == 'backfill':
                        rows = self._backfill(session, engine, code, backfill_from, today)
                        cnt['backfill'] += 1
                        msg = f'백필 {rows}행'
                    else:
                        rows, readjusted = self._incremental(session, engine, code, state,
                                                             backfill_from, today)
                        cnt['incremental'] += 1
                        cnt['readjust'] += int(readjusted)
                        msg = f'수정주가 변동 → 전체 재수집 {rows}행' if readjusted else f'증분 {rows}행'
                    session.commit()        # 종목 단위 커밋
                    cnt['rows'] += rows
                    if kind == 'backfill' or rows > 1 or msg.startswith('수정'):
                        print(f'[{tag}][{idx}] {name}({code}) {msg}', flush=True)
                    idx += 1
                    retry = 0

                except Exception as e:  # noqa: BLE001
                    session.rollback()
                    err = str(e)
                    if ('API 호출 횟수를 초과' in err or isinstance(e, ConnectionError)) \
                            and retry < self.MAX_RETRY:
                        retry += 1
                        print(f'[{tag}][{idx}] {code} 일시 오류({retry}/{self.MAX_RETRY}) → 재시도', flush=True)
                        time.sleep(1 + retry)
                        continue            # idx 유지 → 같은 종목 재시도
                    print(f'[{tag}][{idx}] {name}({code}) 실패: {err}', flush=True)
                    try:
                        self.ohlcvDaoImpl.upsert_state(session, code, last_error=err[:255])
                        session.commit()
                    except Exception:  # noqa: BLE001
                        session.rollback()
                    cnt['failed'] += 1
                    idx += 1
                    retry = 0
        finally:
            session.remove()

        print(f'[{tag}] 청크 완료: {cnt}', flush=True)
        return cnt

    def _backfill(self, session, engine: KisEngine, code: str,
                  backfill_from: date, today: date, readjust_state: dict = None) -> int:
        """5년치 전체 수집 → 종목 전체 교체 → 상태 완료 처리."""
        bars = engine.fetch_daily_bars(code, backfill_from.strftime('%Y%m%d'),
                                       today.strftime('%Y%m%d'), call_gap=self.CALL_GAP)
        if not bars and self.ohlcvDaoImpl.select_bounds(session, code)['bar_cnt']:
            # 이미 쌓인 종목인데 0건이 오면(상폐·일시 장애) 교체하지 않는다 — 지우면 되돌릴 수 없다.
            raise RuntimeError('수집 0건 — 기존 데이터 보존')
        rows = self.ohlcvDaoImpl.replace_bars(session, code, bars)
        state = {**self.ohlcvDaoImpl.select_bounds(session, code),
                 'backfill_done': 'Y', 'last_error': None if bars else '데이터 없음'}
        if readjust_state is not None:
            state['readjust_cnt'] = (readjust_state.get('readjust_cnt') or 0) + 1
            state['last_readjust'] = today
        self.ohlcvDaoImpl.upsert_state(session, code, **state)
        return rows

    def _incremental(self, session, engine: KisEngine, code: str, state: dict,
                     backfill_from: date, today: date):
        """최근 구간 1콜 재조회 → 겹치는 종가 비교 → 같으면 신규분만 UPSERT, 다르면 전체 재수집.

        반환: (적재 행 수, 전체 재수집 여부)
        """
        last = state.get('last_date')
        from_date = (last or today) - timedelta(days=self.OVERLAP_DAYS)
        bars = engine.fetch_daily_bars(code, from_date.strftime('%Y%m%d'),
                                       today.strftime('%Y%m%d'), call_gap=self.CALL_GAP)
        stored = self.ohlcvDaoImpl.select_closes_since(session, code, from_date)

        fetched = {b['trade_date']: b['close_price'] for b in bars}
        common = stored.keys() & fetched.keys()
        changed = [d for d in common if stored[d] != fetched[d]]
        # 저장분이 있는데 겹치는 날이 하나도 없으면 비교가 안 된다(장기 정지 등) → 안전하게 전체 재수집.
        if changed or (stored and not common):
            if changed:
                d = max(changed)
                print(f'[_incremental] {code} 수정주가 변동 감지: {d} 저장 {stored[d]} → 신규 {fetched[d]} '
                      f'(겹친 {len(common)}일 중 {len(changed)}일 상이)', flush=True)
            return self._backfill(session, engine, code, backfill_from, today, readjust_state=state), True

        new_bars = [b for b in bars if last is None or b['trade_date'] >= last]
        rows = self.ohlcvDaoImpl.upsert_bars(session, code, new_bars)
        self.ohlcvDaoImpl.upsert_state(session, code, **self.ohlcvDaoImpl.select_bounds(session, code),
                                       last_error=None)
        return rows, False
