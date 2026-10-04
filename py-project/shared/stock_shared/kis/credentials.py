"""KIS 실전 자격증명 해석 — py-stock-batch / py-naver-stock-theme 공용.

정본 컬럼
    user_detail.kis_id / kis_account / kis_app_key / kis_sec_key

    예전에는 두 앱이 서로 다른 컬럼을 읽었다.
      · batch : kis_app_key / kis_sec_key
      · naver : kis_access_key / kis_secret_key (비면 위 컬럼으로 필드 단위 폴백)
    2026-10-04 확인 결과 user 1~5 모두 kis_app_key/kis_sec_key 가 채워져 있고(36/180자,
    KIS 규격 길이), user 1 은 두 세트의 값이 동일했다. 그래서 batch 쪽을 정본으로 삼는다.

DB 세션
    호출자의 스레드 로컬 세션(dbConn.get_session())을 건드리지 않고 **독립 세션**으로 조회한다.
    예전 구현은 호출자 세션에 close()/remove() 를 호출해서, 자격증명 조회 한 번이 호출자가
    작업 중이던 트랜잭션을 롤백시킬 수 있었다.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Callable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from stock_shared.db.database import dbConn
from stock_shared.models.userDetail import UserDetail

log = logging.getLogger("stock_shared.kis.credentials")

Decrypt = Callable[[str], str]


class KisCredentialError(LookupError, ValueError):
    """자격증명을 구할 수 없을 때(레코드/키 없음).

    LookupError 이면서 ValueError 인 이유 — 두 앱이 서로 다른 타입을 잡아왔다.
      · batch  : 예전 keyLoader 가 LookupError 를 올렸다.
      · naver  : 예전 KisEngine 이 ValueError 를 올렸고, router_profit 이
                 `except ValueError` 로 받아 HTTP 400("등록된 KIS 계정이 없습니다")으로 바꾼다.
                 이 클래스가 ValueError 가 아니면 그 화면이 400 대신 500 을 낸다.
    """


def _as_bool(v: Optional[str], default: bool = True) -> bool:
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def _clean(v) -> str:
    return (v or "").strip()


def _maybe_decrypt(name: str, value: str, decrypt: Optional[Decrypt]) -> str:
    """decrypt 가 주어졌으면 복호화를 시도하고, 실패하면(평문 저장) 원문을 그대로 쓴다.

    이 프로젝트는 키를 평문/암호문 혼용해서 저장해 왔다. 실패를 예외로 올리면
    평문으로 저장된 정상 키가 막히므로 경고만 남기고 통과시킨다.
    """
    if not value or decrypt is None:
        return value
    try:
        return decrypt(value)
    except Exception:  # noqa: BLE001 (패딩/base64 오류 = 평문일 가능성)
        log.warning("%s 복호화 실패 → 평문으로 진행", name)
        return value


def load_creds_from_db(user_id: int, *, decrypt: Optional[Decrypt] = None,
                       strict: bool = False, legacy_fallback: bool = False) -> dict:
    """user_detail 에서 user_id 의 KIS 실전 자격증명을 읽는다. **파일 폴백 없음.**

    반환: {id, account, app_key, sec_key}
    실패: KisCredentialError (LookupError 이자 ValueError)

    strict=False  app_key 만 비어 있지 않으면 통과한다(예전 batch 동작).
                  나머지가 비어도 여기서 막지 않는 이유는 resolve_kis_creds 가 이 예외를
                  "파일 폴백 사유" 로 취급하기 때문이다. 검증을 넓히면 불완전한 행에서
                  조용히 다른 계정의 kis.key 로 넘어가는 경우가 늘어난다.
    strict=True   app_key/sec_key/id/account 가 모두 있어야 통과한다(예전 naver 동작).

    legacy_fallback=True   사용자 설정 화면이 등록한 kis_access_key/kis_secret_key **쌍이 완전하면**
                  그 쌍을 우선한다(예전 naver 동작). 한쪽만 있으면 무시하고 정본 쌍을 쓴다.
                  화면이 정본 컬럼에 쓰도록 바뀌면 이 옵션과 낡은 컬럼 조회를 함께 지운다.
                  batch 는 켜지 않는다 — 낡은 컬럼의 비밀값을 불필요하게 읽지 않기 위해서다.
    """
    cols = [UserDetail.kis_id, UserDetail.kis_account,
            UserDetail.kis_app_key, UserDetail.kis_sec_key]
    if legacy_fallback:
        cols += [UserDetail.kis_access_key, UserDetail.kis_secret_key]

    with Session(dbConn.engine) as s:
        row = s.execute(select(*cols).where(UserDetail.user_id == user_id)).first()

    if row is None:
        raise KisCredentialError(f"user_detail(user_id={user_id}) 레코드를 찾을 수 없습니다.")

    m = row._mapping
    kis_id, account = _clean(m["kis_id"]), _clean(m["kis_account"])
    app_key, sec_key = _clean(m["kis_app_key"]), _clean(m["kis_sec_key"])

    if legacy_fallback:
        l_app, l_sec = _clean(m["kis_access_key"]), _clean(m["kis_secret_key"])
        if l_app and l_sec:          # 완전한 한 쌍일 때만. 한쪽만 있으면 섞이므로 쓰지 않는다.
            app_key, sec_key = l_app, l_sec

    if not app_key or (strict and not sec_key):
        raise KisCredentialError(f"user_detail(user_id={user_id})에 KIS 인증키가 설정되지 않았습니다.")
    if strict and (not kis_id or not account):
        raise KisCredentialError(f"user_detail(user_id={user_id})에 kis_id/kis_account가 설정되지 않았습니다.")

    return {
        "id": m["kis_id"],
        "account": m["kis_account"],
        "app_key": _maybe_decrypt("kis_app_key", app_key, decrypt),
        "sec_key": _maybe_decrypt("kis_sec_key", sec_key, decrypt),
    }


def load_creds_from_file(key_path: str) -> dict:
    """kis.key(JSON) 파일을 그대로 읽는다. 파일이 가진 키 이름을 바꾸지 않는다."""
    try:
        with open(key_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"{key_path} 파일을 찾을 수 없습니다. 경로를 확인해주세요.")
    except json.JSONDecodeError:
        raise ValueError(f"{key_path} 파일의 JSON 형식이 올바르지 않습니다.")


def list_kis_user_ids() -> list[int]:
    """KIS 실전 키(kis_app_key)가 채워진 user_id 목록(오름차순).

    매수추천배치 병렬화에서 '토큰 제공 가능 유저 수 = 분할 병렬 수' 로 쓴다.
    유저를 추가해도 코드 수정 없이 분할 수가 따라간다.
    """
    with Session(dbConn.engine) as s:
        rows = s.execute(
            select(UserDetail.user_id)
            .where(UserDetail.kis_app_key.is_not(None),
                   func.trim(UserDetail.kis_app_key) != "")
            .order_by(UserDetail.user_id)
        ).scalars().all()
    return [int(r) for r in rows]


def resolve_kis_creds(user_id: Optional[int] = None, key_path: str = "kis.key", *,
                      decrypt: Optional[Decrypt] = None) -> dict:
    """batch 정책: DB 우선, 실패하면 파일 폴백.

    우선순위
      1) user_id(인자) 또는 KIS_USER_ID(env) 가 있으면 → DB(user_detail)
      2) DB 실패 & KIS_ALLOW_FILE_FALLBACK != false 이면 → kis.key 파일
      3) user_id 가 전혀 없으면 → kis.key 파일 (단일 운영 방식과 동일)
    """
    if user_id is None:
        env_uid = os.getenv("KIS_USER_ID")
        user_id = int(env_uid) if env_uid else None

    if user_id is None:
        log.info("KIS_USER_ID 미지정 → 파일(%s) 로딩", key_path)
        return load_creds_from_file(key_path)

    try:
        creds = load_creds_from_db(int(user_id), decrypt=decrypt)
        log.info("KIS key DB 로딩")
        return creds
    except Exception as e:  # noqa: BLE001
        if not _as_bool(os.getenv("KIS_ALLOW_FILE_FALLBACK"), default=True):
            raise
        log.warning("DB 로딩 실패(user_id=%s): %s → 파일(%s) fallback", user_id, e, key_path)
        return load_creds_from_file(key_path)
