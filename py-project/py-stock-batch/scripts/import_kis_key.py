"""
1회성 이관 스크립트: kis.key(JSON) → user_detail 의 KIS 컬럼(secret 은 AES 암호화).
app 모듈(aesUtils, dbConn)을 그대로 재사용한다.

사전조건: sql/20260727_add_kis_keys.sql 실행 완료.

사용법(레포 루트에서):
  python -m scripts.import_kis_key --user-id 1 --key-file kis.key
  python -m scripts.import_kis_key --user-id 1 --key-file kis.key --dry-run
"""
import argparse
import json
import sys

from sqlalchemy import text

from app.common.utils.aesUtils import aesUtils
from app.config.database import dbConn

_UPDATE = text(
    """
    UPDATE user_detail SET
      kis_id = :kis_id,
      kis_account = :kis_account,
      kis_app_key = :kis_app_key,
      kis_sec_key = :kis_sec_key,
      kis_virtual_id = :kis_virtual_id,
      kis_virtual_account = :kis_virtual_account,
      kis_vir_app_key = :kis_vir_app_key,
      kis_vir_sec_key = :kis_vir_sec_key
    WHERE user_id = :user_id
    """
)


def _enc(v):
    return aesUtils.encrypt(v) if v else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-id", type=int, required=True)
    ap.add_argument("--key-file", required=True, help="kis.key JSON 경로")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(args.key_file, encoding="utf-8") as f:
        k = json.load(f)

    params = {
        "user_id": args.user_id,
        "kis_id": k.get("id"),
        "kis_account": k.get("account"),
        "kis_app_key": _enc(k.get("app_key")),
        "kis_sec_key": _enc(k.get("sec_key")),
        "kis_virtual_id": k.get("virtual_id"),
        "kis_virtual_account": k.get("virtual_account"),
        "kis_vir_app_key": _enc(k.get("vir_app_key")),
        "kis_vir_sec_key": _enc(k.get("vir_sec_key")),
    }

    masked = {kk: ("***" if kk.endswith("key") and vv else vv) for kk, vv in params.items()}
    print(f"[import] user_id={args.user_id} params={masked}")

    if args.dry_run:
        print("[dry-run] DB 쓰기 생략")
        return 0

    session = dbConn.get_session()
    try:
        res = session.execute(_UPDATE, params)
        session.commit()
        if res.rowcount == 0:
            print(f"[경고] user_id={args.user_id} 행이 없어 UPDATE 안 됨. user_detail 먼저 생성 필요.", file=sys.stderr)
            return 2
    finally:
        session.close()
    print(f"[완료] user_id={args.user_id} KIS key 이관 성공")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
