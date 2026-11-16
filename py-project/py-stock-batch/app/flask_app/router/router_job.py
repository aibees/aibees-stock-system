from datetime import datetime
from flask import Blueprint, request, g, jsonify

from app.scheduler_app.runner import scheduleManage, run_job_once
from app.flask_app.utils.apiResponse import ApiResponse
from app.flask_app.utils.auth import require_admin

job_bp = Blueprint("jobs", __name__)
# 배치 실행·재적재·상태 조회는 관리자만(관리자 토큰 또는 X-Batch-Key). 웹 nginx 가 /api/v1/jobs 를 그대로 넘기므로
# 예전엔 주소만 알면 누구나 배치를 돌릴 수 있었다. 자동 스케줄(APScheduler)은 HTTP 를 거치지 않아 영향이 없다.
# BATCHES ROUTE ROOT :: TEST
# ===============================================================================
@job_bp.route("")
def jobs_index():
    return {
        'msg': 'test'
    }
    
@job_bp.route("/start")
@require_admin
def schedule_start():
    pass


@job_bp.route("/stop")
@require_admin
def schedule_stop():
    pass


@job_bp.route("/once/<job_id>", methods=["POST"])
@require_admin
def schedule_run_once(job_id):
    try:
        job = scheduleManage.scheduler.get_job(job_id)
        if not job:
            return ApiResponse.success({
                'id': job_id,
                'msg': '실행할 Job이 없습니다.',
                'status': 'fail'
            })

        params = request.get_json() or {}
        manual_run_id = f"{job_id}_manual_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        print(manual_run_id)
        # 별도 프로세스(ProcessPoolExecutor)로 실행 → gunicorn worker 를 블로킹하지 않음.
        #   기존 in-worker daemon Thread 방식은 batch 의 CPU-bound 구간이 GIL 을 잡아
        #   worker heartbeat 를 끊어 WORKER TIMEOUT(SIGABRT)을 유발했다.
        #   job.args = [module_name, class_name] (load_jobs 가 _execute_job 으로 등록).
        module_name, class_name = job.args[0], job.args[1]
        run_job_once(module_name, class_name, **{**(job.kwargs or {}), **params})

        return ApiResponse.success({
            'id': job_id,
            'manual_run_id': manual_run_id,
            'msg': '배치 작업이 백그라운드에서 성공적으로 실행 요청되었습니다.',
            'status': 'success',
            'params_used': params
        })

    except Exception as e:
        return ApiResponse.error(str(e))


@job_bp.route("/reload")
@require_admin
def schedule_reload():
    try:
        scheduleManage.load_jobs()
        
        return ApiResponse.success(__get_schedule_status())
    except Exception as e:
        return ApiResponse.error(str(e))


@job_bp.route("/status")
@require_admin
def schedule_status():
    try:
        return ApiResponse.success(__get_schedule_status())
    except Exception as e:
        return ApiResponse.error(str(e))
    
def __get_schedule_status():
    
    jobs = scheduleManage.scheduler.get_jobs()
    return [
        {
            "id": job.id,
            "next_run_time": str(job.next_run_time),
            "trigger": str(job.trigger),
            "func": f"{job.func.__module__}.{job.func.__name__}"
        }
        for job in jobs
    ]


@job_bp.route("/running", methods=["GET"])
@require_admin
def schedule_running():
    try:
        running_jobs = []

        # APScheduler 내부 executor의 _instances 속성을 통해 현재 돌고 있는 job_id를 찾습니다.
        # _instances는 { 'job_id': 실행중인_인스턴스_수 } 형태의 딕셔너리입니다.
        for executor_name, executor in scheduleManage.scheduler._executors.items():
            if hasattr(executor, '_instances'):
                for job_id, instance_count in executor._instances.items():
                    if instance_count > 0:
                        job = scheduleManage.scheduler.get_job(job_id)

                        if job:
                            # 일반적인 반복 스케줄 작업인 경우
                            running_jobs.append({
                                "id": job.id,
                                "name": job.name,
                                "func": f"{job.func.__module__}.{job.func.__name__}",
                                "trigger": str(job.trigger),
                                "running_instances": instance_count,
                                "executor": executor_name
                            })
                        else:
                            # /once API 등으로 생성된 1회성(date) 작업은 실행 즉시 스케줄러
                            # 목록에서 지워지므로 get_job()으로 조회되지 않을 수 있습니다.
                            running_jobs.append({
                                "id": job_id,
                                "running_instances": instance_count,
                                "executor": executor_name,
                                "note": "Job details unavailable (likely a one-off task)"
                            })

        return ApiResponse.success(running_jobs)

    except Exception as e:
        return ApiResponse.error(str(e))