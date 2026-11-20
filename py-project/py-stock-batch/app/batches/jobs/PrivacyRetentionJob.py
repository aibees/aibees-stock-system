"""개인정보 보관 기간이 지난 기록을 파기하는 배치(양봉상회 yangbong 스키마).

목적
    개인정보 처리방침(yangbong-static-vue Privacy.vue 3항)이 약속한 보관 기간을 지킨다.
    기간을 바꾸면 처리방침도 함께 고친다. 법정 기간이라 공통코드로 바꿀 수 있게 두지 않는다.

    접속 기록(user_login_log, user_menu_access_log) : 3개월 (통신비밀보호법)
        단 관리자(user_auth ADMIN) 기록은 1년 — 개인정보 안전성 확보조치 기준(개인정보취급자 접속기록 1년 이상)
    앱 푸시 기기 토큰(device_push_token)            : 꺼진(enabled_flag='N') 뒤 30일
        (꺼진 토큰도 같은 기기가 다시 등록하면 upsert 로 살아나므로 바로 지우지 않고 잠시 둔다)

DB
    배치 계정(stock)은 yangbong 스키마에도 DELETE 권한이 있어 스키마를 붙여 지운다.
    한 번에 BATCH 행씩 나눠 지우고 매번 커밋한다(테이블을 오래 잠그지 않게).

실행
    매일 04:30 (KST). batch_job_master 등록은 sql/stock/004_privacy_retention_job.sql.

수동 실행
    POST /api/v1/jobs/once/PRIVACY_RETENTION_JOB
    body: {"dry_run": true}   지우지 않고 대상 건수만 센다
"""
from sqlalchemy import text

from app.batches.jobs.job import Job

SCHEMA = 'yangbong'
ACCESS_LOG_MONTHS = 3
ADMIN_ACCESS_LOG_MONTHS = 12
PUSH_TOKEN_DISABLED_DAYS = 30
BATCH = 5000
MAX_ROUNDS = 200          # 한 항목 최대 100만 행 — 밀린 기록이 많아도 배치를 오래 붙잡지 않게(다음 날 이어서)

# 관리자 = user_auth 의 ADMIN 권한(사용 중). 탈퇴로 user_auth 가 지워진 사람은 일반 기간을 따른다.
_ADMIN_IDS = f"SELECT user_id FROM {SCHEMA}.user_auth WHERE auth_id = 'ADMIN' AND enabled_flag = 'Y'"


def _targets():
    """(이름, WHERE 절, 테이블) — 일반 3개월 / 관리자 1년 / 꺼진 푸시 토큰 30일."""
    out = []
    for table in ('user_login_log', 'user_menu_access_log'):
        # 일반 회원·비회원(user_id NULL — 로그인 실패 등): 3개월
        out.append((f"{table}(일반 {ACCESS_LOG_MONTHS}개월)", f"{SCHEMA}.{table}",
                    f"created_date < NOW() - INTERVAL {ACCESS_LOG_MONTHS} MONTH "
                    f"AND (user_id IS NULL OR user_id NOT IN ({_ADMIN_IDS}))"))
        # 관리자 포함 전원: 1년
        out.append((f"{table}(관리자 {ADMIN_ACCESS_LOG_MONTHS}개월)", f"{SCHEMA}.{table}",
                    f"created_date < NOW() - INTERVAL {ADMIN_ACCESS_LOG_MONTHS} MONTH"))
    out.append((f"device_push_token(꺼진 뒤 {PUSH_TOKEN_DISABLED_DAYS}일)", f"{SCHEMA}.device_push_token",
                f"enabled_flag = 'N' AND updated_at < NOW() - INTERVAL {PUSH_TOKEN_DISABLED_DAYS} DAY"))
    return out


class PrivacyRetentionJob(Job):

    def __init__(self):
        super().__init__()
        self.job_name = 'PrivacyRetentionJob'
        self.push_notify = False   # 매일 도는 정리 작업 — 시작/종료 알림은 끈다(실패 알림은 그대로 간다)

    def get_name(self):
        return self.job_name

    def run_batch(self, **kwargs):
        dry_run = str(kwargs.get('dry_run', '')).lower() in ('1', 'true', 'y', 'yes')
        result, failed = {}, []
        for name, table, where in _targets():
            if dry_run:
                result[name] = self.session.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {where}")).scalar()
                continue
            total = 0
            try:
                for _ in range(MAX_ROUNDS):
                    n = self.session.execute(text(f"DELETE FROM {table} WHERE {where} LIMIT {BATCH}")).rowcount
                    self.session.commit()
                    total += n
                    if n < BATCH:
                        break
            except Exception as e:  # noqa: BLE001 — 한 항목이 실패해도 나머지는 지운다
                self.session.rollback()
                failed.append(f"{name}: {e}"[:120])
            result[name] = total

        print(f"[PrivacyRetentionJob] {'대상(dry_run)' if dry_run else '삭제'} {result}", flush=True)
        desc = ('[dry_run] ' if dry_run else '') + ', '.join(f"{k} {v}" for k, v in result.items())
        if failed:
            # 일부 실패도 FAIL 로 남겨 운영자 알림(실패 push)이 가게 한다
            return {'status': 'FAIL', 'batch_cnt': sum(result.values()),
                    'desc': (f"일부 실패 — {'; '.join(failed)} | {desc}")[:255]}
        return {'status': 'SUCCESS', 'batch_cnt': sum(result.values()), 'desc': desc[:255]}
