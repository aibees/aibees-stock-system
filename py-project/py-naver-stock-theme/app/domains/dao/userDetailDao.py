from sqlalchemy import select

from stock_shared.models.userDetail import UserDetail

import logging

logging.basicConfig(level=logging.ERROR)


class UserDetailDao:
    def __init__(self):
        self.__name__ = 'UserDetailDao'

    # select KIS 인증정보 (kis_id, kis_account, app_key, sec_key)
    # ================================================================
    def select_kis_credentials(self, session, user_id: int):
        """
        user_detail 에서 KIS 실투자 인증정보를 조회합니다.
        반환: {id, account, app_key, sec_key} 또는 None

        키 컬럼이 두 벌 있다 — 이 앱은 원래 kis_access_key/kis_secret_key 만 읽었고
        py-stock-batch(worker/배치)는 kis_app_key/kis_sec_key 를 읽는다. 실제 데이터는
        **user_id=1 만** 앞쪽 두 벌이 채워져 있고 나머지 유저는 뒤쪽만 채워져 있다
        (그래서 KisEngine 이 _KIS_USER_ID=1 로 단일계정 고정이었다).
        유저별 조회(매매손익 화면 등)가 1번 유저 말고도 동작해야 하므로,
        앞쪽이 비어 있으면 뒤쪽으로 fallback 한다.

        두 벌 모두 평문 저장이다(실측: app_key 36자 / sec_key 180자 = KIS 규격 길이).
        py-stock-batch 쪽은 과거 암호문 혼용 가능성 때문에 AES 복호화를 시도하고
        실패 시 평문으로 진행하는데, 이 앱에는 aes.key 가 없고 현재 데이터가 전부
        평문이라 복호화 단계를 두지 않는다. 암호문이 섞이기 시작하면 그때
        py-stock-batch 의 aesUtils 를 이 앱에도 들여와야 한다.
        """
        stmt = select(
            UserDetail.kis_id,
            UserDetail.kis_account,
            UserDetail.kis_access_key,
            UserDetail.kis_secret_key,
            UserDetail.kis_app_key,
            UserDetail.kis_sec_key,
        ).where(
            UserDetail.user_id == user_id
        )

        row = session.execute(stmt).first()
        if row is None:
            return None

        def _pick(primary, fallback):
            """빈 문자열도 '없음'으로 본다 — user_id=5 의 kis_access_key 가
            NULL 이 아니라 '' 로 들어와 있어 NULL 체크만으로는 걸러지지 않는다."""
            v = (primary or "").strip()
            return v if v else (fallback or "").strip() or None

        return {
            'id': row.kis_id,
            'account': row.kis_account,
            'app_key': _pick(row.kis_access_key, row.kis_app_key),
            'sec_key': _pick(row.kis_secret_key, row.kis_sec_key),
        }

    # select UPBIT 인증정보 (access, secret)
    # ================================================================
    def select_upbit_credentials(self, session, user_id: int):
        """
        user_detail 에서 UPBIT 인증정보를 조회합니다.
        반환: {access, secret} 또는 None
        """
        stmt = select(
            UserDetail.upbit_access_key,
            UserDetail.upbit_secret_key,
        ).where(
            UserDetail.user_id == user_id
        )

        row = session.execute(stmt).first()
        if row is None:
            return None

        return {
            'access': row.upbit_access_key,
            'secret': row.upbit_secret_key,
        }
