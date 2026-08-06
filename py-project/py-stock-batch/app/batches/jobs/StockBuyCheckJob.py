import pprint
import time

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

from app.batches.jobs.job import Job
from app.batches.services.stockService import StockService
from app.batches.services.userService import UserService
from app.common.utils.smtpUtils import emailUtils
from app.ext_services.kis.KisEngine import KisEngine
from app.ext_services.kis.keyLoader import list_kis_user_ids
from app.ext_services.kis.component.KisStockService import KisService
from stock_shared.strategy.kospi1 import KospiStrategy1
from stock_shared.dto.userOptionMeta import UserOptionMeta


class StockBuyCheckJob(Job):
    def __init__(self):
        super().__init__()
        self.job_name = 'StockBuyCheckJob'
        self.stockServiceImpl = StockService()
        self.userServiceImpl = UserService()
        # KIS 엔진/서비스는 run_batch 에서 유저별(스레드별)로 생성한다.
        # (여기서 미리 만들지 않음 — 병렬 워커가 각자 고유 appkey 엔진을 사용)

    def get_name(self):
        return self.job_name

    @staticmethod
    def _make_strategy(strategy_param: str):
        """전략 인스턴스 생성. 스레드별로 독립 인스턴스를 만들어 상태 공유를 피한다."""
        if strategy_param == 'KOSPI_2':
            return KospiStrategy1()  # TODO : more strategy
        return KospiStrategy1()

    @staticmethod
    def _split_even(items: list, n: int) -> list:
        """items 를 최대 n 개의 연속 청크로 단순 분할(부하 불균형은 무시)."""
        if n <= 1:
            return [items]
        size = (len(items) + n - 1) // n  # ceil
        return [items[i:i + size] for i in range(0, len(items), size)] or [[]]

    ####################################################
    # 배치 시작
    ####################################################
    def run_batch(self, **kwargs):
        # Variable Setting
        today = date.today()

        stock_list = self.stockServiceImpl.get_stock_master_list(self.session, 'batches')
        stock_option_meta: UserOptionMeta = self.userServiceImpl.get_user_options(self.session)

        end_date = kwargs.get('end_date', today.strftime('%Y-%m-%d'))
        start_date = kwargs.get('start_date', (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=250)).strftime('%Y-%m-%d'))
        strategy_param = kwargs.get('strategy', 'KOSPI_1')
        ymd = end_date.replace('-', '')

        # 배치 시작 전: 해당 ymd 기존 데이터 삭제
        deleted_cnt = self.stockServiceImpl.clean_buy_target_stock_by_ymd(self.session, ymd)
        self.session.commit()
        print(f'[{ymd}] 기존 데이터 {deleted_cnt}건 삭제 완료', flush=True)

        print(f'배치 대상 stock size : {len(stock_list)}', flush=True)

        # ── KIS 토큰 제공 가능 유저 수 = 분할 병렬 수 (현재 2, 향후 3 등 가변) ──
        #   유저별 KIS_USER_ID 로 각각 다른 appkey(=독립 rate limit)의 KisEngine 을 만든다.
        #   유저가 없으면(=파일 단일 운영) KisEngine() 1개로 직렬 동작(기존과 동일).
        try:
            uids = list_kis_user_ids()
        except Exception as e:
            print(f"[run_batch] KIS 유저 조회 실패 → 파일 단일 엔진 fallback: {e}", flush=True)
            uids = []

        engines = []
        for uid in uids:
            try:
                engines.append((uid, KisEngine(user_id=uid)))
            except Exception as e:
                print(f"[run_batch] user_id={uid} 엔진 생성 실패 → 제외: {e}", flush=True)
        if not engines:
            # 유저 엔진이 하나도 없으면 파일 단일 엔진으로 직렬 동작(기존과 동일)
            engines = [(None, KisEngine())]

        n = len(engines)
        chunks = self._split_even(stock_list, n)
        print(f"병렬 분할: 유저 {n}명 → 청크 {[len(c) for c in chunks]}", flush=True)

        # ── 스레드는 KIS 조회+지표계산만 수행(무 DB). 결과(비-HOLD)만 리턴 ──
        result_list = []
        with ThreadPoolExecutor(max_workers=n) as ex:
            futures = []
            for (uid, engine), chunk in zip(engines, chunks):
                if not chunk:
                    continue
                futures.append(ex.submit(
                    self._process_chunk,
                    uid, engine, chunk, strategy_param, stock_option_meta,
                    start_date, end_date, ymd,
                ))
            for f in futures:
                try:
                    result_list.extend(f.result())
                except Exception as e:
                    print(f"[run_batch] 워커 실패: {e}", flush=True)

        # ── 메인 스레드: 후보 전체 모은 뒤 랭크 산정 → 한 번에 저장 ──
        if result_list:
            result_list = self.stockServiceImpl.assign_ranks(result_list)
            try:
                self.stockServiceImpl.save_buy_target_stocks_bulk(self.session, result_list)
                self.session.commit()
                print(f"매수타겟 일괄 저장 완료: {len(result_list)}건 (랭크 포함)", flush=True)
            except Exception as e:
                self.session.rollback()
                print(f"[일괄 저장 실패] {e}", flush=True)
                raise

        return_result = {
            'status': 'success',
            'batch_cnt': len(stock_list),
            'desc': '매수 기대기준에 충족하는 종목이 없습니다.' if len(result_list) == 0 else f'매수 기대기준에 충족하는 종목은 총 {len(result_list)}개 입니다.'
        }
        print(f"result ==> {len(result_list)}", flush=True)

        # 이메일 전송 (rank_no 오름차순으로 정렬해 발송)
        mail_sorted = sorted(result_list, key=lambda x: x.get('rank_no', 10 ** 9))
        created_html = self.stockServiceImpl.create_mail_html(mail_sorted)
        email_list = self.userServiceImpl.get_user_email_by_condition(self.session, 'email')
        for email in email_list:
            self.send_mail_buy_target_stock(created_html, email, len(result_list))

        return return_result

    ####################################################
    # 청크 워커 (스레드) — KIS 조회 + 지표계산만. DB 접근 금지.
    #   각 스레드는 자기 KisEngine(고유 appkey) 과 독립 KisService/전략 인스턴스를 사용한다.
    #   반환: 비-HOLD 결과 dict 리스트.
    ####################################################
    def _process_chunk(self, uid, engine: KisEngine, chunk: list, strategy_param: str,
                       stock_option_meta: UserOptionMeta, start_date: str, end_date: str, ymd: str) -> list:
        tag = f"u{uid}" if uid is not None else "file"
        kis_service = KisService()          # 스레드 로컬
        strategy = self._make_strategy(strategy_param)
        results = []
        idx = 0

        while idx < len(chunk):
            stock = chunk[idx]
            stock_code = stock.get('stock_code')
            stock_name = stock.get('stock_name')
            print(f"[{tag}][{idx}] {stock_name}({stock_code})", flush=True)

            try:
                time.sleep(1.5)

                # 매수추천배치 일봉 조회: 국내주식기간별시세 API(FHKST03010100) 사용
                ohlcv = engine.get_daily_ohlcv(stock_code, start_date, end_date)
                if ohlcv is None:
                    print(f"[{tag}] 조회 불가 종목 ==> {stock_name}({stock_code})", flush=True)
                    idx += 1
                    continue

                last_close = ohlcv.iloc[-1]['close']
                if last_close < 1000:
                    print(f"[{tag}] skip ==> 1000원 이하 종목", flush=True)
                    idx += 1
                    continue

                last_volume = ohlcv.iloc[-1]['volume']
                if last_volume < stock_option_meta.vol_limit:
                    print(f"[{tag}] skip ==> 거래량 미달 / volume={last_volume}", flush=True)
                    idx += 1
                    continue

                fin_result = engine.get_finance_info(stock_code)

                computed = kis_service.compute_indicator_df(ohlcv, user_info=stock_option_meta)
                computed.fillna(0.0, inplace=True)
                trade_data = computed.to_dict(orient='records')

                result = strategy.get_result_with_action(trade_data, stock_option_meta)
                if result['action_type'] != 'HOLD':
                    result['stock_code'] = stock_code
                    result['stock_name'] = stock_name
                    result['ymd'] = ymd
                    result['fin'] = fin_result
                    pprint.pprint(result)
                    results.append(result)

                idx += 1

            except ConnectionError:
                print(f"[{tag}][{idx}] 네트워크 오류 → 3초 후 재시도...\n", flush=True)
                time.sleep(3)
                continue  # idx 유지 → 동일 종목 재시도

            except Exception as e:
                print(f"[{tag}] {str(e)}\n", flush=True)
                if "API 호출 횟수를 초과" in str(e):
                    print(f"[{tag}] 한번 더 호출....", flush=True)
                    time.sleep(1)
                    continue  # idx 유지 → 재시도
                idx += 1
                continue

        print(f"[{tag}] 청크 완료: 후보 {len(results)}건", flush=True)
        return results


    # smtpUtils.py 파일에서 emailUtils 객체를 임포트한다고 가정합니다.
    # from smtpUtils import emailUtils

    def send_mail_buy_target_stock(self, email_body: str, email_to: str, data_len: int):

        subject = f"[자동알림] 매수 타겟 종목 분석 결과 (총 {data_len}건)"
        # 4. 메일 발송
        # emailUtils 인스턴스 환경에 맞게 호출
        response = emailUtils.sendMail(subject=subject, body=email_body, receipt=email_to)

        if response.get('result') == 'success':
            print(f"✅ 성공적으로 '{email_to}' 주소로 분석 결과를 발송했습니다.", flush=True)
        else:
            print(f"❌ 메일 발송 실패: {response.get('msg')}", flush=True)
