"""월별 추천 성과(홈 '전월 추천 성과')를 미리 계산해 저장하는 배치.

목적
    홈 화면이 야후 일봉을 매번 받아 계산하지 않도록, 전월 성과를
    trade_buy_target_perf_monthly 에 저장해 둔다. 계산 로직은
    stock_shared.analytics.reco_performance 단일 출처(API 와 공유).

확정
    월말 추천 종목은 다음 달 초 5거래일이 지나야 값이 정해진다. 그래서 확정 전에는
    매일 다시 계산하고, 확정(final_flag='Y')된 달은 건너뛴다 → 매월 초 2주 남짓만 실제로 일한다.

외부 호출
    yfinance 일괄 다운로드 1회(전월 추천 종목 수만큼, 약 10초). KIS 호출 0건.

실행
    매 평일 21:50 (KST). 매수추천(20:00)·캔들 백필(21:30)·라벨(21:40) 이후.
    batch_job_master 등록은 sql/30_buy_target_perf_monthly.sql 참고.

수동 실행
    POST /api/v1/jobs/once/RECO_PERF_JOB
    body:
      {"ym": "202609"}              특정 월(기본: 전월)
      {"ym": "202609", "force": true} 확정된 달도 다시 계산(계산 기준을 바꿨을 때)
"""
from app.batches.jobs.job import Job
from stock_shared.analytics.reco_performance import prev_month, refresh_month


class RecoPerformanceJob(Job):

    def __init__(self):
        super().__init__()
        self.job_name = 'RecoPerformanceJob'

    def get_name(self):
        return self.job_name

    def run_batch(self, **kwargs):
        ym = str(kwargs.get('ym') or prev_month())
        force = str(kwargs.get('force', '')).lower() in ('1', 'true', 'y', 'yes')

        result = refresh_month(self.session, ym, force=force)
        print(f"[RecoPerformanceJob] {result}", flush=True)

        if result['skipped']:
            return {'status': 'SUCCESS', 'batch_cnt': 0,
                    'desc': f"{ym} 확정 완료 상태 — 건너뜀"}
        return {
            'status': 'SUCCESS',
            'batch_cnt': result['evaluated_count'] or 0,
            'desc': f"{ym} 추천 성과 {result['evaluated_count']}종목 계산 "
                    f"({'확정' if result['final'] else '미확정 — 내일 다시 계산'})",
        }
