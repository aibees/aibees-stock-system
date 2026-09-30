"""shape 모델 아티팩트의 저장/백업/승격 — 파일시스템 조작 단일 출처.

디렉터리 구조 (shared/stock_shared/ml/artifacts/):
    shape_gbm_v1.joblib                      ← 라이브. shape_model 이 읽는 유일한 파일.
    candidates/shape_gbm_{run_id}.joblib     ← 매 학습의 후보(승격 여부 무관, 항상 남김).
    backup/shape_gbm_v1_{run_id}.joblib      ← 승격 직전 라이브의 사본(롤백용).

왜 후보를 항상 남기는가
    게이트에서 탈락한 모델도 "왜 나빠졌는지" 를 나중에 봐야 한다. 후보 파일이 없으면
    지표 숫자만 남고 재현이 안 된다. 용량은 1개 400KB 수준이라 주 1회 적립은 무해하다.

왜 원자적 교체가 필요한가
    라이브 파일에 직접 쓰는 중에 StockBuyCheckJob(다른 프로세스)이 joblib.load 를 하면
    깨진 파일을 읽는다. 같은 파일시스템의 임시파일에 쓴 뒤 os.replace 로 바꾸면
    교체가 원자적이라 읽는 쪽은 항상 구버전 아니면 신버전 중 하나를 온전히 본다.
"""
from __future__ import annotations

import logging
import os
import shutil

from stock_shared.ml import shape_model

log = logging.getLogger("stock_shared.ml.shape_artifact")

_ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
CANDIDATES_DIR = os.path.join(_ARTIFACTS_DIR, "candidates")
BACKUP_DIR = os.path.join(_ARTIFACTS_DIR, "backup")

# 백업 보관 개수. 넘치면 오래된 것부터 지운다(롤백은 보통 직전 1~2개로 끝난다).
BACKUP_KEEP = 10


def _ensure_dirs() -> None:
    os.makedirs(CANDIDATES_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)


def save_candidate(model, run_id: str) -> str:
    """후보 모델을 candidates/ 에 저장하고 경로를 반환한다."""
    import joblib

    _ensure_dirs()
    path = os.path.join(CANDIDATES_DIR, f"shape_gbm_{run_id}.joblib")
    joblib.dump(model, path)
    log.info("[shape_artifact] 후보 저장: %s", path)
    return path


def promote(candidate_path: str, run_id: str) -> dict:
    """후보를 라이브로 승격한다. 반환: {'backup_path', 'live_path'}.

    1) 현재 라이브를 backup/ 으로 복사(있으면) — 롤백 경로 확보.
    2) 후보를 라이브와 같은 디렉터리의 임시파일로 복사.
    3) os.replace 로 라이브 경로에 원자적 교체.
    """
    _ensure_dirs()
    live = shape_model.artifact_path()

    backup_path = None
    if os.path.exists(live):
        backup_path = os.path.join(BACKUP_DIR, f"shape_gbm_v1_{run_id}.joblib")
        shutil.copy2(live, backup_path)
        log.info("[shape_artifact] 라이브 백업: %s", backup_path)

    tmp = f"{live}.tmp.{run_id}"
    try:
        shutil.copy2(candidate_path, tmp)
        os.replace(tmp, live)          # 원자적 — 읽는 쪽이 깨진 파일을 보지 않는다
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    log.info("[shape_artifact] 승격 완료: %s → %s", candidate_path, live)
    _prune_backups()
    return {"backup_path": backup_path, "live_path": live}


def _prune_backups(keep: int = BACKUP_KEEP) -> int:
    """오래된 백업 정리. 반환: 삭제 개수."""
    try:
        files = sorted(
            (os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR)
             if f.endswith(".joblib")),
            key=os.path.getmtime,
            reverse=True,
        )
    except FileNotFoundError:
        return 0
    removed = 0
    for p in files[keep:]:
        try:
            os.remove(p)
            removed += 1
        except OSError as e:  # noqa: PERF203
            log.warning("[shape_artifact] 백업 삭제 실패 %s: %s", p, e)
    return removed


def load_live():
    """라이브 아티팩트를 **캐시 없이** 새로 읽는다(게이트의 라이브 채점용).

    shape_model.score() 를 쓰면 1건씩만 채점되고 캐시된 싱글톤에 묶인다.
    게이트는 holdout 수천 행을 한 번에 채점해야 하므로 모델 객체가 직접 필요하다.
    """
    import joblib

    live = shape_model.artifact_path()
    if not os.path.exists(live):
        log.warning("[shape_artifact] 라이브 아티팩트 없음: %s", live)
        return None
    try:
        return joblib.load(live)
    except Exception as e:  # noqa: BLE001 — sklearn 버전 불일치 등
        log.warning("[shape_artifact] 라이브 로드 실패(%s): %s", type(e).__name__, e)
        return None
