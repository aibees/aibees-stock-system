"""
KIS 자격증명 로더.

worker 컨테이너는 KIS_USER_ID(=1/2/3) 만 다르게 하여 같은 이미지로 뜬다.
이 로더가 그 값으로 user_detail 에서 자기 유저의 KIS key 를 조회·복호화한다.

우선순위:
  1) user_id(인자) 또는 KIS_USER_ID(env) 가 있으면 → DB(user_detail) 조회
  2) DB 실패 & KIS_ALLOW_FILE_FALLBACK != false 이면 → kis.key 파일 fallback
  3) user_id 가 전혀 없으면 → kis.key 파일 (기존 단일 운영 방식과 동일)

반환 dict 키(KisEngine 이 기대하는 형태): id, account, app_key, sec_key (실전 전용)

전제: user_detail 에 KIS 컬럼이 존재해야 한다 (sql/20260727_add_kis_keys.sql).
secret 계열(kis_app_key/kis_sec_key)은 AES 암호화 저장.
"""
import json
import logging
import os

from sqlalchemy import text

from app.common.utils.aesUtils import aesUtils
from app.config.database import dbConn

log = logging.getLogger("kis.keyLoader")

_KIS_COLS = "kis_id, kis_account, kis_app_key, kis_sec_key"


def _as_bool(v, default=True):
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def _maybe_decrypt(name, value):
    """AES 복호화 시도. 실패하면(평문 저장인 경우) 원문 그대로 사용.
    이 프로젝트는 upbit 키를 평문 저장하는 등 혼용되어 있어, KIS 키도 평문/암호문 모두 허용한다."""
    if not value:
        return value
    try:
        return aesUtils.decrypt(value)
    except Exception as e:  # noqa: BLE001  (패딩/base64 오류 = 평문일 가능성)
        log.warning(f"{name} 복호화 실패 → 평문으로 진행")
        return value


def _load_from_db(user_id: int) -> dict:
    sql = text(f"SELECT {_KIS_COLS} FROM user_detail WHERE user_id = :uid")
    session = dbConn.get_session()
    try:
        row = session.execute(sql, {"uid": user_id}).mappings().first()
    finally:
        session.close()

    if row is None:
        raise LookupError("사용자 별 설정값이 누락되어 있습니다.")
    if not row["kis_app_key"]:
        raise LookupError(f"user_id={user_id} 의 KIS key 가 비어 있습니다. (사용자 설정 점검 필요)")

    return {
        "id": row["kis_id"],
        "account": row["kis_account"],
        "app_key": _maybe_decrypt('kis_app_key', row["kis_app_key"]),
        "sec_key": _maybe_decrypt('kis_sec_key', row["kis_sec_key"]),
    }


def _load_from_file(key_path: str) -> dict:
    try:
        with open(key_path, "r", encoding="utf-8") as f:
            return json.load(f)  # kis.key 는 이미 KisEngine 이 기대하는 키를 가짐
    except FileNotFoundError:
        raise FileNotFoundError(f"{key_path} 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
    except json.JSONDecodeError:
        raise ValueError(f"{key_path} 파일의 JSON 형식이 올바르지 않습니다.")


def list_kis_user_ids() -> list[int]:
    """KIS 실전 자격증명(kis_app_key)이 채워진 user_id 목록을 오름차순으로 반환.
    매수추천배치 병렬화에서 '토큰 제공 가능 유저 수 = 분할 병렬 수' 로 사용한다.
    (현재 2명 → 향후 3명 등 가변. 코드 수정 없이 유저 수에 따라 분할 수가 따라감.)

    ※ user_detail 의 KIS 컬럼은 ORM 모델(UserDetail)에 매핑돼 있지 않아
      keyLoader 와 동일하게 raw SQL 로 조회한다."""
    sql = text(
        "SELECT user_id FROM user_detail "
        "WHERE kis_app_key IS NOT NULL AND TRIM(kis_app_key) != '' "
        "ORDER BY user_id"
    )
    session = dbConn.get_session()
    try:
        rows = session.execute(sql).scalars().all()
    finally:
        session.close()
    return [int(r) for r in rows]


def resolve_kis_creds(user_id=None, key_path: str = "kis.key") -> dict:
    """user_id/env 기준으로 실전 자격증명을 해석해 dict 로 반환."""
    if user_id is None:
        env_uid = os.getenv("KIS_USER_ID")
        user_id = int(env_uid) if env_uid else None

    # (3) user_id 없음 → 파일
    if user_id is None:
        log.info("KIS_USER_ID 미지정 → 파일(%s) 로딩", key_path)
        return _load_from_file(key_path)

    # (1) DB 조회
    try:
        creds = _load_from_db(int(user_id))
        log.info("KIS key DB 로딩")
        return creds
    except Exception as e:  # noqa: BLE001
        if not _as_bool(os.getenv("KIS_ALLOW_FILE_FALLBACK"), default=True):
            raise
        log.warning("DB 로딩 실패(user_id=%s): %s → 파일(%s) fallback", user_id, e, key_path)
        # (2) 파일 fallback
        return _load_from_file(key_path)
