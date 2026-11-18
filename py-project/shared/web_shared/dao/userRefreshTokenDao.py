"""
[신규] UserRefreshTokenDao

user_refresh_token 테이블에 대한 CRUD 연산을 제공하는 DAO.

주요 메서드:
  - insert_token        : 신규 refreshToken 저장
  - find_by_token       : 토큰 문자열로 행 조회
  - revoke_token        : 단일 토큰 폐기 (is_revoked = True)
  - revoke_all_by_user  : 특정 사용자의 모든 토큰 일괄 폐기 (재사용 감지 시 사용)
  - delete_expired      : 만료된 토큰 물리 삭제 (배치 정리용, 선택적 호출)
"""

from datetime import datetime
from sqlalchemy import select, update, delete
from app.domains.models.userRefreshToken import UserRefreshToken


class UserRefreshTokenDao:
    def __init__(self):
        self.__name__ = 'UserRefreshTokenDao'

    def insert_token(self, session, user_id: int, token: str, expires_at: datetime) -> UserRefreshToken:
        """
        [신규] 새 refreshToken을 DB에 저장하고 저장된 객체를 반환

        Parameters:
            session    : SQLAlchemy DB 세션
            user_id    : 토큰 소유자의 user_id
            token      : secrets.token_urlsafe() 로 생성한 불투명 토큰 문자열
            expires_at : 토큰 만료 시각 (UTC datetime)

        Returns:
            저장된 UserRefreshToken 인스턴스
        """
        new_token = UserRefreshToken(
            user_id=user_id,
            token=token,
            expires_at=expires_at,
            is_revoked=False,
            created_at=datetime.utcnow()
        )
        session.add(new_token)
        # flush() 로 DB에 INSERT를 실행하되, 트랜잭션은 유지
        # → caller(authService)가 커밋 타이밍을 결정할 수 있게 함
        session.flush()
        return new_token

    def find_by_token(self, session, token: str) -> UserRefreshToken | None:
        """
        [신규] 토큰 문자열로 DB에서 행을 조회

        주로 /api/oauth/refresh 호출 시 토큰의 존재·폐기·만료 여부를
        검증하는 데 사용됨.

        Returns:
            일치하는 UserRefreshToken 인스턴스, 없으면 None
        """
        stmt = select(UserRefreshToken).where(
            UserRefreshToken.token == token
        )
        return session.execute(stmt).scalars().first()

    def revoke_token(self, session, token: str) -> None:
        """
        [신규] 특정 토큰 단건 폐기

        /api/oauth/refresh 에서 토큰 Rotation 시, 기존 토큰을 폐기하고
        새 토큰 쌍을 발급하기 전에 호출됨.
        /api/oauth/logout 에서도 현재 토큰을 폐기할 때 사용됨.

        물리 삭제 대신 is_revoked = True 로 설정해 보안 감사 로그 보존.
        """
        stmt = (
            update(UserRefreshToken)
            .where(UserRefreshToken.token == token)
            .values(is_revoked=True)
        )
        session.execute(stmt)

    def revoke_all_by_user(self, session, user_id: int) -> None:
        """
        [신규] 특정 사용자의 모든 유효 토큰 일괄 폐기

        재사용 감지(Rotation Detection) 시 사용:
            → 이미 폐기된 토큰으로 /refresh 를 시도하면 탈취 가능성이 있으므로
              해당 사용자의 모든 세션을 강제 만료시켜 보안 사고를 억제함

        명세 인용:
            "동일 refreshToken이 두 번 사용되면 해당 사용자 전체 세션 강제 만료"
        """
        stmt = (
            update(UserRefreshToken)
            .where(
                UserRefreshToken.user_id == user_id,
                UserRefreshToken.is_revoked == False  # noqa: E712
            )
            .values(is_revoked=True)
        )
        session.execute(stmt)

    def delete_expired(self, session) -> int:
        """
        [신규] 만료된 토큰 물리 삭제 (선택적 정기 배치 호출용)

        is_revoked 여부와 관계없이 expires_at 이 현재 시각보다 이전인
        행을 모두 삭제해 테이블이 무한 증가하지 않도록 관리.

        Returns:
            삭제된 행의 수
        """
        stmt = delete(UserRefreshToken).where(
            UserRefreshToken.expires_at < datetime.utcnow()
        )
        result = session.execute(stmt)
        return result.rowcount
