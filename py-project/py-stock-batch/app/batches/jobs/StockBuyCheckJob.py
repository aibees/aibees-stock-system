import pprint
import time

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import pandas as pd

from app.batches.jobs.job import Job
from app.batches.services.stockService import StockService
from app.batches.services.userService import UserService
from app.common.utils.smtpUtils import emailUtils
from app.common.constants.Literal import Literal
from app.ext_services.kis.KisEngine import KisEngine
from app.ext_services.kis.keyLoader import list_kis_user_ids
from app.ext_services.kis.component.KisStockService import KisService
from stock_shared.strategy.kospi1 import KospiStrategy1
from stock_shared.dto.userOptionMeta import UserOptionMeta
from stock_shared.ml.shape_features import SHAPE_FEATURE_COLUMNS
from stock_shared.ml.shape_model import score as shape_score


# 최근 N일(캘린더) 내 매수추천에 등장했던 종목은 오늘 다시 조건을 만족해도
# rank_no 산정에서 신규 종목보다 후순위로 밀린다(완전 제외 아님 — 그날 신규 후보가
# 없으면 재등장 종목도 여전히 rank1이 될 수 있다). 같은 종목 연속 반복 매수 완화 목적.
# (2026-08-08 추가. 값만 바꾸면 즉시 적용됨.)
REPEAT_PENALTY_DAYS = 5

# Home.vue 매수타겟 카드 간이차트용 슬라이스 길이(영업일). trade_buy_target_chart 저장.
CHART_DAYS = 120

# ── 2단계(top10 → 모멘텀 합성 재정렬) 매수추천 — 2026-09 세션 후속 리서치 ──────────
# KospiStrategy1 watch 신호(기존 경로, "watch 게이트")와 **병행**으로 동작한다.
# 전종목(get_stock_master_list) 중 watch 신호 통과 여부와 무관하게 아래 안정성
# 필터를 통과한 종목 전체를 모아, shape+OBV 모델 상위 10개를 추린 뒤, 같은 계열
# 모멘텀 지표(OBV/MACD/RSI/거래량)로 재정렬한 1위를 종합picks 1위로 삼는다.
# 편향 없는 전종목 스캔(2,608~2,664종목) 기준 여러 학습 cutoff 에서 재현된 결과:
# 단독 top1 대비 승률 +5~9%p 개선(승률 13.6%→22.7%, 평균net_edge +1.11%p→+3.80%p 등).
COMPOSITE_TOP_N = 10
COMPOSITE_PENNY_PRICE_MIN = 1000
COMPOSITE_EXTREME_MOVE_PCT = 15.0      # 최근 COMPOSITE_EXTREME_LOOKBACK일 내 이 이상 등락 있으면 제외
COMPOSITE_EXTREME_LOOKBACK = 10
COMPOSITE_ATR_RATIO_MAX = 0.10         # ATR/종가 상한(kospi1.atr_ratio_min=0.05 하한과 별개)
COMPOSITE_SMA20_TREND_BARS = 14        # 14봉 전 대비 sma20(ema20 필드) 상승 여부
# 모멘텀 합성점수 = 아래 5개를 그날 후보 pool 내 z-score 로 정규화한 평균.
COMPOSITE_MOMENTUM_COLS = ['obv_gap_norm', 'obv_slope3', 'ind_vol_ratio_today', 'ind_macd_hist_norm']


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
    def _build_chart_data(trade_data: list) -> list:
        """최근 CHART_DAYS 영업일의 OHLCV+SMA(5/20/60/120) 슬림 슬라이스.
        trade_data 는 compute_indicator_df() 가 만든 지표 20여 개 포함 전체 컬럼이라,
        간이차트(봉차트+이평선)에 불필요한 컬럼(MACD/BB/ATR/OBV 등)은 제외하고 필요한 것만 뽑는다."""
        rows = trade_data[-CHART_DAYS:]
        return [
            {
                "date": r.get(Literal.DATETIME),
                "open": r.get(Literal.OPEN),
                "high": r.get(Literal.HIGH),
                "low": r.get(Literal.LOW),
                "close": r.get(Literal.CLOSE),
                "volume": r.get(Literal.VOLUME),
                "ma20": r.get(Literal.EMA_20),
                "ma60": r.get(Literal.EMA_60),
                "ma120": r.get(Literal.EMA_120),
            }
            for r in rows
        ]

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
        deleted_chart_cnt = self.stockServiceImpl.clean_buy_target_chart_by_ymd(self.session, ymd)
        self.session.commit()
        print(f'[{ymd}] 기존 데이터 {deleted_cnt}건(차트 {deleted_chart_cnt}건) 삭제 완료', flush=True)

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
        composite_pool = []
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
                    chunk_results, chunk_composite = f.result()
                    result_list.extend(chunk_results)
                    composite_pool.extend(chunk_composite)
                except Exception as e:
                    print(f"[run_batch] 워커 실패: {e}", flush=True)

        # ── 2단계(top10→모멘텀 재정렬) — watch 게이트와 병행 저장 ──────────
        #   watch 게이트를 안 거친 종목이어도 trade_buy_target_stock 행은 OHLCV/지표가
        #   항상 채워져 있어야 한다 — 그래서 "전체 행" upsert(save_buy_target_stocks_bulk)
        #   를 먼저 태우고, composite 전용 필드(momentum_composite/composite_rank_no)는
        #   그 다음에 별도 upsert 한다. 이 전체 행 upsert를 **watch 게이트 저장(아래)보다
        #   먼저** 실행해야 한다 — 같은 종목이 양쪽 다 해당되는 날, watch 게이트 쪽이
        #   나중에 real score/rank_no/재무정보로 다시 덮어써야 하기 때문이다(순서 반대면
        #   watch 게이트가 채운 score/rank_no 를 이 블록이 NULL 로 되돌려버린다).
        try:
            composite_top10 = self._compute_composite_top10(composite_pool, ymd)
            if composite_top10:
                empty_fin = {'eps': None, 'pbr': None, 'per': None, 'roe': None, 'peg': None}
                full_rows = [
                    {
                        'ymd': item['ymd'],
                        'stock_code': item['stock_code'],
                        'stock_name': item['stock_name'],
                        'action_type': item['action_type'],
                        'todayStock': item['todayStock'],
                        'indicator': item['indicator'],
                        'fin': empty_fin,
                        'chart_data': item['chart_data'],
                        'shape_proba': item['shape_proba'],
                    }
                    for item in composite_top10
                ]
                self.stockServiceImpl.save_buy_target_stocks_bulk(self.session, full_rows)
                self.stockServiceImpl.save_buy_target_chart_bulk(self.session, full_rows)
                self.stockServiceImpl.save_composite_top10(self.session, composite_top10)
                self.session.commit()
                print(f"2단계 top10 저장 완료: {len(composite_top10)}건 (OHLCV/지표 포함) "
                      f"(1위: {composite_top10[0]['stock_name']}({composite_top10[0]['stock_code']}))", flush=True)
            else:
                print("2단계 후보 pool 이 비어있어(안정성 필터 통과 종목 없음) top10 미생성", flush=True)
        except Exception as e:
            self.session.rollback()
            print(f"[2단계 top10 저장 실패, watch 게이트 결과는 유지됨] {e}", flush=True)

        # ── 메인 스레드: 후보 전체 모은 뒤 랭크 산정 → 한 번에 저장 ──
        if result_list:
            try:
                recent_codes = self.stockServiceImpl.get_recent_target_codes(
                    self.session, ymd, REPEAT_PENALTY_DAYS)
            except Exception as e:
                print(f"[run_batch] 최근 추천 이력 조회 실패(재추천 페널티 미적용): {e}", flush=True)
                recent_codes = set()
            result_list = self.stockServiceImpl.assign_ranks(result_list, recent_codes=recent_codes)
            try:
                self.stockServiceImpl.save_buy_target_stocks_bulk(self.session, result_list)
                self.session.commit()
                print(f"매수타겟 일괄 저장 완료: {len(result_list)}건 (랭크 포함)", flush=True)
            except Exception as e:
                self.session.rollback()
                print(f"[일괄 저장 실패] {e}", flush=True)
                raise

            # 간이차트 저장은 부가기능이라 실패해도 본 배치(매수타겟/이메일)를 막지 않는다.
            try:
                self.stockServiceImpl.save_buy_target_chart_bulk(self.session, result_list)
                self.session.commit()
                print(f"매수타겟 간이차트 저장 완료: {len(result_list)}건", flush=True)
            except Exception as e:
                self.session.rollback()
                print(f"[간이차트 저장 실패, 매수타겟 저장은 유지됨] {e}", flush=True)

        return_result = {
            'status': 'SUCCESS',
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

    @staticmethod
    def _compute_composite_top10(composite_pool: list, ymd: str) -> list:
        """2단계 후보 pool 전체(안정성 필터 통과분)에서 top10 을 추리고 모멘텀
        합성점수로 재정렬한다. z-score 는 그날 pool 전체 기준(top10 으로 좁히기 전)
        이어야 한다 — 리서치 검증 당시와 동일 조건."""
        if not composite_pool:
            return []

        pool = pd.DataFrame(composite_pool).dropna(subset=['proba'] + COMPOSITE_MOMENTUM_COLS + ['ind_rsi14'])
        if pool.empty:
            return []

        def _zscore(s: pd.Series) -> pd.Series:
            std = s.std()
            return (s - s.mean()) / std if std and std > 0 else s * 0.0

        for col in COMPOSITE_MOMENTUM_COLS:
            pool[f'z_{col}'] = _zscore(pool[col])
        pool['z_rsi_centered'] = _zscore(pool['ind_rsi14'] - 50)
        z_cols = [f'z_{c}' for c in COMPOSITE_MOMENTUM_COLS] + ['z_rsi_centered']
        pool['momentum_composite'] = pool[z_cols].mean(axis=1)

        top10 = pool.sort_values('proba', ascending=False).head(COMPOSITE_TOP_N)
        top10 = top10.sort_values('momentum_composite', ascending=False).reset_index(drop=True)
        top10['composite_rank_no'] = range(1, len(top10) + 1)

        return [
            {
                'ymd': ymd,
                'stock_code': r['stock_code'],
                'stock_name': r['stock_name'],
                'close': r['close'],
                'shape_proba': round(float(r['proba']), 4),
                'momentum_composite': round(float(r['momentum_composite']), 4),
                'composite_rank_no': int(r['composite_rank_no']),
                # watch 게이트를 안 거쳤어도 OHLCV/지표는 항상 채워야 한다 — 아래에서
                # save_buy_target_stocks_bulk(전체 행 upsert)에 그대로 넘길 원본.
                'action_type': r['action_type'],
                'todayStock': r['today_stock'],
                'indicator': r['indicator'],
                'chart_data': r['chart_data'],
            }
            for _, r in top10.iterrows()
        ]

    @staticmethod
    def _composite_eligible(computed: pd.DataFrame, stock: dict) -> bool:
        """2단계(top10→모멘텀 재정렬) 후보 안정성 필터. watch 게이트와 무관하게 별도 평가한다."""
        if str(stock.get('admin_issue') or 'N').upper() == 'Y':
            return False
        if str(stock.get('trading_halt') or 'N').upper() == 'Y':
            return False
        if len(computed) < COMPOSITE_SMA20_TREND_BARS + 1:
            return False

        last = computed.iloc[-1]
        close = float(last.get(Literal.CLOSE) or 0)
        if close <= 0:
            return False

        ema20_now = float(last.get(Literal.EMA_20) or 0)
        ema20_prev = float(computed.iloc[-1 - COMPOSITE_SMA20_TREND_BARS].get(Literal.EMA_20) or 0)
        if not (ema20_now > ema20_prev):
            return False

        # 장기 추세 필터: 저가(low) > sma120(ema120 필드). 매수 필수 조건(kospi1.py와 동일).
        low_today = float(last.get(Literal.LOW) or 0)
        ema120_now = float(last.get(Literal.EMA_120) or 0)
        if ema120_now <= 0 or not (low_today > ema120_now):
            return False

        atr_ratio = float(last.get(Literal.ATR) or 0) / close
        if atr_ratio > COMPOSITE_ATR_RATIO_MAX:
            return False

        recent = computed.tail(COMPOSITE_EXTREME_LOOKBACK + 1)[Literal.CLOSE].astype(float)
        daily_ret_pct = recent.pct_change().abs() * 100
        if (daily_ret_pct >= COMPOSITE_EXTREME_MOVE_PCT).any():
            return False

        if bool(last.get('shape_exhaustion_flag', False)):
            return False

        return True

    ####################################################
    # 청크 워커 (스레드) — KIS 조회 + 지표계산만. DB 접근 금지.
    #   각 스레드는 자기 KisEngine(고유 appkey) 과 독립 KisService/전략 인스턴스를 사용한다.
    #   반환: (watch게이트 결과 dict 리스트, 2단계 후보 lightweight dict 리스트) 튜플.
    ####################################################
    def _process_chunk(self, uid, engine: KisEngine, chunk: list, strategy_param: str,
                       stock_option_meta: UserOptionMeta, start_date: str, end_date: str, ymd: str):
        tag = f"u{uid}" if uid is not None else "file"
        kis_service = KisService()          # 스레드 로컬
        strategy = self._make_strategy(strategy_param)
        results = []
        composite_pool = []
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
                if last_close < COMPOSITE_PENNY_PRICE_MIN:
                    print(f"[{tag}] skip ==> 1000원 이하 종목", flush=True)
                    idx += 1
                    continue

                last_volume = ohlcv.iloc[-1]['volume']
                if last_volume < stock_option_meta.vol_limit:
                    print(f"[{tag}] skip ==> 거래량 미달 / volume={last_volume}", flush=True)
                    idx += 1
                    continue

                computed = kis_service.compute_indicator_df(ohlcv, user_info=stock_option_meta)
                # 2단계 소진게이트 판정은 fillna(0.0) 전에(0으로 뭉개지면 오탐 발생) 미리 해둔다.
                last_row_raw = computed.iloc[-1]
                is_exh = bool(
                    (last_row_raw.get('shape_bars_since_min', 0) or 0) >= 13
                    and (last_row_raw.get('shape_total_ret_14', 0) or 0) >= 0.25
                    and (last_row_raw.get('shape_ret_1d_today', 0) or 0) >= 0.10
                )
                computed['shape_exhaustion_flag'] = False
                computed.iloc[-1, computed.columns.get_loc('shape_exhaustion_flag')] = is_exh

                computed.fillna(0.0, inplace=True)
                trade_data = computed.to_dict(orient='records')

                result = strategy.get_result_with_action(trade_data, stock_option_meta)

                # shape+OBV proba 는 watch 게이트 통과 여부와 무관하게 항상 계산한다
                # (2단계 병행 후보 선정에 필요 — 2026-09 세션 후속 리서치).
                last_features = {c: trade_data[-1].get(c) for c in SHAPE_FEATURE_COLUMNS}
                shape_proba = shape_score(last_features)

                if result['action_type'] != 'HOLD':
                    fin_result = engine.get_finance_info(stock_code)
                    result['stock_code'] = stock_code
                    result['stock_name'] = stock_name
                    result['ymd'] = ymd
                    result['fin'] = fin_result
                    result['chart_data'] = self._build_chart_data(trade_data)
                    result['shape_proba'] = shape_proba
                    pprint.pprint(result)
                    results.append(result)

                if shape_proba is not None and self._composite_eligible(computed, stock):
                    # watch 게이트 통과 여부와 무관하게, trade_buy_target_stock 에 들어갈
                    # 행은 항상 OHLCV/지표가 채워져 있어야 한다 — result['todayStock']/
                    # ['indicator'] 는 이미 매 종목 계산돼 있으니(위 get_result_with_action)
                    # 그대로 참조만 하면 된다(재계산/재조회 불필요).
                    composite_pool.append({
                        'stock_code': stock_code,
                        'stock_name': stock_name,
                        'close': float(last_close),
                        'proba': shape_proba,
                        'obv_gap_norm': last_features.get('obv_gap_norm'),
                        'obv_slope3': last_features.get('obv_slope3'),
                        'ind_vol_ratio_today': last_features.get('ind_vol_ratio_today'),
                        'ind_macd_hist_norm': last_features.get('ind_macd_hist_norm'),
                        'ind_rsi14': last_features.get('ind_rsi14'),
                        'action_type': result['action_type'],
                        'today_stock': result['todayStock'],
                        'indicator': result['indicator'],
                        'chart_data': self._build_chart_data(trade_data),
                    })

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

        print(f"[{tag}] 청크 완료: watch게이트 후보 {len(results)}건 / 2단계 pool {len(composite_pool)}건", flush=True)
        return results, composite_pool


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
