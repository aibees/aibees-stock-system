"""배치 Job 실행 전용 모듈.

┌─ 이 모듈의 유일한 불변식 ────────────────────────────────────────┐
│  **import side-effect 를 절대 만들지 않는다.**                    │
│  모듈 레벨에서 DB 접속·스레드 기동·스케줄러 생성 금지.             │
└──────────────────────────────────────────────────────────────────┘

이유: 자식 프로세스(spawn)는 `_execute_job` 을 되살리려고 이 모듈을
     처음부터 재import 한다. 여기에 전역 객체 생성이 있으면
     자식이 job 을 돌리기도 전에 그걸 다시 세우다 죽거나 멈춘다.

     실제로 예전엔 `_execute_job` 이 runner.py 에 있었고, runner.py 끝에
     `scheduleManage = StockScheduler()` 가 있었다. 그래서 자식이
     부팅할 때마다 스케줄러를 통째로 다시 만들었다.
     (/once 호출 뒤 로그에 "APScheduler Job Load.... / JOB REGISTERED"
      가 찍힌 게 부모가 아니라 **자식 프로세스**가 남긴 흔적이다.)

     → runner.py 에서 이 모듈로 분리한 이유가 그것이다.
       runner.py 를 여기서 import 하지 마라(순환 + side-effect 부활).
"""
import importlib
import logging
import multiprocessing
import threading
import traceback
from concurrent.futures import ProcessPoolExecutor, BrokenExecutor

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
#  멀티프로세싱 컨텍스트 — fork 금지, spawn 고정.
#
#  gunicorn worker 는 멀티스레드 프로세스다:
#    · APScheduler BackgroundScheduler 스레드
#    · 그 내부 processpool 의 executor-manager / queue-feeder 스레드
#    · SQLAlchemy scoped_session 풀
#
#  POSIX fork() 는 **호출한 스레드 하나만** 자식으로 넘긴다.
#  나머지 스레드는 사라지는데, 그 스레드들이 쥐고 있던 락은
#  '잠긴 상태 그대로' 자식 메모리에 복사된다. 풀어줄 주인이 없으니
#  자식이 그 락을 건드리는 순간 영원히 멈춘다.
#
#  _execute_job 의 첫 두 줄이 정확히 그 지뢰다:
#    engine.dispose()          → SQLAlchemy 풀 락
#    importlib.import_module() → 인터프리터 import 락
#  그래서 자식은 print 한 줄 못 남기고 굳는다. 예외가 아니라 hang 이라
#  로그도 없고 Future 도 영원히 pending —— /once 무반응의 정체.
#
#  spawn 은 빈 인터프리터로 새로 뜨므로 상속된 락 자체가 없다.
#  (Python 3.12 는 멀티스레드 fork 에 DeprecationWarning 을 띄우고,
#   3.14 부터는 Linux 기본값도 fork 가 아니다. 미리 맞춰두는 셈.)
#
#  APScheduler 3.11 의 ProcessPoolExecutor 는 이미 spawn 을 기본으로
#  쓴다. 즉 cron 자동실행은 spawn, /once 수동실행만 fork 였다.
#  같은 코드가 자동은 되고 수동만 안 되던 이유가 이 비대칭이다.
# ──────────────────────────────────────────────────────────────
MP_CONTEXT = multiprocessing.get_context("spawn")


def _execute_job(module_name: str, class_name: str, **kwargs):
    """자식 프로세스 진입점. 스케줄 실행·수동 실행이 공용으로 쓴다.

    module-level 함수여야 한다. bound method 를 넘기면 인스턴스 전체를
    pickle 하려 들고, KisEngine(PyKis 세션)·ThreadPoolExecutor 같은
    직렬화 불가 객체 때문에 PicklingError 가 난다.
    module-level 함수는 "모듈 경로 + 함수명" 만으로 직렬화된다.

    예외는 여기서 반드시 찍고 다시 raise 한다. 부모가 Future.result()
    를 안 읽어도 컨테이너 stdout 에는 스택이 남아야 하기 때문이다.
    """
    try:
        # 자식 전용 엔진을 새로 잡는다. spawn 이라 부모 풀을 물려받지
        # 않지만, 혹시 다른 컨텍스트로 돌더라도 소켓 FD 공유를 막는다.
        from app.config.database import dbConn
        dbConn.engine.dispose()

        jobModule = importlib.import_module(module_name)
        jobClass = getattr(jobModule, class_name)
        print(f"[JOB START] {module_name}.{class_name} kwargs={kwargs}", flush=True)

        jobClass().process(**kwargs)

        print(f"[JOB DONE] {module_name}.{class_name}", flush=True)
    except Exception:
        print(f"[JOB FAILED] {module_name}.{class_name}\n{traceback.format_exc()}",
              flush=True)
        raise


# ──────────────────────────────────────────────────────────────
#  수동 실행(/once) 전용 ProcessPoolExecutor.
#
#  web worker 안 daemon Thread 로 돌리면 batch 의 CPU-bound 구간이
#  GIL 을 오래 잡아 worker heartbeat 가 끊기고, gunicorn arbiter 가
#  WORKER TIMEOUT 으로 worker 를 죽인다(→ daemon Thread 도 같이 사망).
#  그래서 별도 프로세스로 분리한다. 단 위 MP_CONTEXT 주석대로 spawn 으로.
# ──────────────────────────────────────────────────────────────
_manual_executor = None
_manual_lock = threading.Lock()


def _get_manual_executor(reset: bool = False) -> ProcessPoolExecutor:
    """수동 실행 풀 획득. reset=True 면 기존 풀을 버리고 새로 만든다."""
    global _manual_executor
    with _manual_lock:
        if reset and _manual_executor is not None:
            try:
                _manual_executor.shutdown(wait=False)
            except Exception:  # noqa: BLE001
                pass
            _manual_executor = None
        if _manual_executor is None:
            _manual_executor = ProcessPoolExecutor(
                max_workers=3, mp_context=MP_CONTEXT
            )
        return _manual_executor


def run_job_once(module_name: str, class_name: str, **kwargs):
    """수동(/once) batch 를 web worker 밖 별도 프로세스로 submit(비블로킹).

    반환: concurrent.futures.Future — 호출측은 대기하지 않는다.
    호출측이 result() 를 안 읽어도 실패가 묻히지 않도록 done callback 에서
    예외를 로그로 흘린다. (예전엔 Future 를 그냥 버려서, 자식이 터지든
     pool 이 깨지든 로그 한 줄 없이 조용히 사라졌다.)
    """
    tag = f"{module_name}.{class_name}"
    try:
        executor = _get_manual_executor()
        future = executor.submit(_execute_job, module_name, class_name, **kwargs)
    except BrokenExecutor:
        # 이전 자식이 죽으면서 풀이 통째로 망가진 상태. 새 풀로 1회 재시도.
        log.warning("[JOB] manual pool broken → 재생성 후 재시도: %s", tag)
        executor = _get_manual_executor(reset=True)
        future = executor.submit(_execute_job, module_name, class_name, **kwargs)

    def _on_done(f):
        try:
            f.result()
        except Exception as e:  # noqa: BLE001
            log.error("[JOB FAILED] %s: %s\n%s", tag, e, traceback.format_exc())
            print(f"[JOB FAILED] {tag}: {e}", flush=True)

    future.add_done_callback(_on_done)
    return future
