import threading
import importlib
import logging
from datetime import datetime
from flask import Blueprint, request, g

from app.domains.dao.batchJobMasterDao import BatchJobMasterDao
from app.domains.dao.nBatchLogDao import BatchLogDao
from app.flask_app.utils.apiResponse import ApiResponse
from app.config.db.database import dbConn

logging.basicConfig(level=logging.ERROR)

batch_bp = Blueprint("batches", __name__)

batchJobMasterDaoImpl = BatchJobMasterDao()
batchLogDaoImpl = BatchLogDao()


# BATCHES ROUTE ROOT :: TEST
# ===============================================================================
@batch_bp.route("/")
def batches_index():
    return {
        'msg': 'aibees flask :: batches home'
    }


# ===============================================================================
# 1. BatchSetting.vue - batch_job_master CRUD / 단독실행
# ===============================================================================

# 1-1. 배치 목록 조회
# -------------------------------------------------------------------------------
@batch_bp.route("/master/batch-jobs", methods=['GET'])
def select_batch_job_list():
    try:
        results = batchJobMasterDaoImpl.select_all(g.db)
        return ApiResponse.success(sorted(results, key=lambda x: x['job_id']))
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error(str(e))


# 1-2. 배치 등록
# -------------------------------------------------------------------------------
@batch_bp.route("/master/batch-jobs", methods=['POST'])
def insert_batch_job():
    data = request.get_json(silent=True) or {}
    job_id = data.get('job_id')

    if not job_id:
        return ApiResponse.error("job_id는 필수입니다.")

    try:
        exists = batchJobMasterDaoImpl.select_by_job_id(g.db, job_id)
        if exists:
            return ApiResponse.error(f"이미 등록된 job_id 입니다. (job_id={job_id})", status=409)

        batchJobMasterDaoImpl.insert(g.db, data)
        g.db.commit()

        return ApiResponse.success(batchJobMasterDaoImpl.select_by_job_id(g.db, job_id))
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error(str(e))


# 1-3. 배치 수정
# -------------------------------------------------------------------------------
@batch_bp.route("/master/batch-jobs/<job_id>", methods=['PUT'])
def update_batch_job(job_id):
    data = request.get_json(silent=True) or {}

    try:
        exists = batchJobMasterDaoImpl.select_by_job_id(g.db, job_id)
        if not exists:
            return ApiResponse.error(f"존재하지 않는 job_id 입니다. (job_id={job_id})", status=404)

        data['job_id'] = job_id
        batchJobMasterDaoImpl.update_by_key(g.db, data)
        g.db.commit()

        return ApiResponse.success(batchJobMasterDaoImpl.select_by_job_id(g.db, job_id))
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error(str(e))


# 1-4. 사용/미사용 토글 (PATCH)
# -------------------------------------------------------------------------------
@batch_bp.route("/master/batch-jobs/<job_id>", methods=['PATCH'])
def patch_batch_job_enabled(job_id):
    data = request.get_json(silent=True) or {}
    enabled_flag = data.get('enabled_flag')

    if enabled_flag not in ('Y', 'N'):
        return ApiResponse.error("enabled_flag 값은 'Y' 또는 'N' 이어야 합니다.")

    try:
        exists = batchJobMasterDaoImpl.select_by_job_id(g.db, job_id)
        if not exists:
            return ApiResponse.error(f"존재하지 않는 job_id 입니다. (job_id={job_id})", status=404)

        batchJobMasterDaoImpl.update_by_key(g.db, {'job_id': job_id, 'enabled_flag': enabled_flag})
        g.db.commit()

        return ApiResponse.success({'job_id': job_id, 'enabled_flag': enabled_flag})
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error(str(e))


# 1-5. 배치 삭제
# -------------------------------------------------------------------------------
@batch_bp.route("/master/batch-jobs/<job_id>", methods=['DELETE'])
def delete_batch_job(job_id):
    try:
        exists = batchJobMasterDaoImpl.select_by_job_id(g.db, job_id)
        if not exists:
            return ApiResponse.error(f"존재하지 않는 job_id 입니다. (job_id={job_id})", status=404)

        batchJobMasterDaoImpl.delete_by_key(g.db, {'job_id': job_id})
        g.db.commit()

        return ApiResponse.success(True)
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error(str(e))


# 1-6. 배치 단독실행
# -------------------------------------------------------------------------------
@batch_bp.route("/batch/execute/<job_id>", methods=['POST'])
def execute_batch_job(job_id):
    run_params = request.get_json(silent=True)
    if run_params is None:
        run_params = {}

    try:
        job = batchJobMasterDaoImpl.select_by_job_id(g.db, job_id)
        if not job:
            return ApiResponse.error(f"존재하지 않는 배치입니다. (job_id={job_id})", status=404)

        if job['enabled_flag'] != 'Y':
            return ApiResponse.error("비활성화된 배치입니다.", status=400)

        batch_seq = batchLogDaoImpl.next_batch_seq(g.db)
        batchLogDaoImpl.insert_batch_log(g.db, {
            'batch_seq': batch_seq,
            'batch_code': job_id,
            'start_time': datetime.now(),
            'desc': '단독실행 요청',
        })
        g.db.commit()

        # 배치 클래스 동적 실행 (비동기)
        threading.Thread(
            target=_run_batch_job,
            args=(batch_seq, job, run_params),
            daemon=True,
        ).start()

        return ApiResponse.success({'batch_seq': batch_seq, 'status': 'RUNNING'})
    except Exception as e:
        g.db.rollback()
        logging.exception(e)
        return ApiResponse.error(str(e))


def _run_batch_job(batch_seq, job, run_params):
    """
    별도 스레드에서 module_name / class_name 으로 배치 클래스를 동적 로딩하여 실행하고,
    실행 결과(batch_cnt / status / desc / end_time)를 stock_batch_log 에 업데이트한다.
    """
    session = dbConn.get_session()
    status = 'FAIL'
    desc = ''
    batch_cnt = 0

    try:
        module = importlib.import_module(job['module_name'])
        job_class = getattr(module, job['class_name'])
        instance = job_class()

        # run() / execute() 중 존재하는 메서드를 실행
        if hasattr(instance, 'run'):
            result = instance.run(run_params)
        elif hasattr(instance, 'execute'):
            result = instance.execute(run_params)
        else:
            raise AttributeError(f"{job['class_name']} 에 run/execute 메서드가 없습니다.")

        if isinstance(result, dict):
            batch_cnt = result.get('batch_cnt', 0) or 0
            desc = result.get('desc', '정상 종료')
        else:
            desc = '정상 종료'

        status = 'SUCCESS'
    except Exception as e:
        logging.exception(e)
        status = 'FAIL'
        desc = str(e)[:256]
    finally:
        try:
            batchLogDaoImpl.update_batch_log(session, {
                'batch_seq': batch_seq,
                'status': status,
                'desc': desc,
                'batch_cnt': batch_cnt,
                'end_time': datetime.now(),
            })
            session.commit()
        except Exception as e:
            logging.exception(e)
            session.rollback()
        finally:
            session.remove()


# ===============================================================================
# 2. BatchLogSetting.vue - stock_batch_log 단순 조회 (Pageable)
# ===============================================================================

# 2-1. 배치 로그 목록 조회
# -------------------------------------------------------------------------------
@batch_bp.route("/batch-logs", methods=['GET'])
def select_batch_log_page():
    try:
        page = int(request.args.get('page', 0))
        size = int(request.args.get('size', 20))
    except (TypeError, ValueError):
        return ApiResponse.error("page / size 파라미터는 숫자여야 합니다.")

    if page < 0:
        page = 0
    if size <= 0:
        size = 20

    try:
        items = batchLogDaoImpl.select_batch_log_page(g.db, page, size)
        total_elements = batchLogDaoImpl.count_batch_log(g.db)
        total_pages = (total_elements + size - 1) // size if size else 0

        return ApiResponse.success(items, extra={
            'totalPages': total_pages,
            'totalElements': total_elements,
            'page': page,
            'size': size,
        })
    except Exception as e:
        logging.exception(e)
        return ApiResponse.error(str(e))
