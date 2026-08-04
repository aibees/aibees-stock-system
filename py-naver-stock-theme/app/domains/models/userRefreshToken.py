"""
[신규] user_refresh_token 테이블 ORM 모델

refreshToken을 DB에 저장해 서버 측 폐기(revoke)를 가능하게 하는 모델.

■ 테이블 생성 DDL (참고용):
    CREATE TABLE user_refresh_token (
        id           INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
        user_id      INT          NOT NULL,
        token        VARCHAR(255) NOT NULL UNIQUE,
        expires_at   DATETIME     NOT NULL,
        is_revoked   TINYINT(1)   NOT NULL DEFAULT 0,
        created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

■ 설계 의도:
    - token 컬럼에 UNIQUE 제약을 두어, 동일 토큰이 DB에 두 번 삽입되는
      것을 방지하고 재사용 감지(Rotation) 시 식별자로 활용함
    - is_revoked 플래그로 토큰을 물리 삭제하지 않고 논리적으로 폐기해
      감사 로그(audit trail) 확보 및 재사용 감지에 활용 가능
"""

from sqlalchemy import Column, String, Integer, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class UserRefreshToken(Base):
    __tablename__ = 'user_refresh_token'

    # 자동 증가 PK — 개별 토큰 행을 식별하는 내부 키
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 토큰 소유자 — UserMaster.user_id 와 논리적으로 연결됨
    # (FK 제약은 마이그레이션 전략에 따라 선택적으로 추가)
    user_id = Column(Integer, nullable=False)

    # 불투명 토큰(opaque token) 문자열
    # secrets.token_urlsafe(64) 로 생성한 암호학적으로 안전한 랜덤값
    # UNIQUE 제약으로 재사용 감지(Rotation Detection)에 활용
    token = Column(String(255), nullable=False, unique=True)

    # 이 토큰의 만료 시각 (UTC 기준)
    # 만료 여부: expires_at < datetime.utcnow()
    expires_at = Column(DateTime, nullable=False)

    # 서버 측 강제 폐기 플래그
    # - True  : 폐기됨 → 재사용 감지 또는 /logout 호출로 무효화된 토큰
    # - False : 유효 상태
    # 물리 삭제 대신 플래그를 쓰는 이유: 재사용 시도(보안 이슈) 감지 후
    # 해당 사용자의 전체 세션 강제 만료 시 어떤 토큰이 침해됐는지 추적 가능
    is_revoked = Column(Boolean, nullable=False, default=False)

    # 토큰 발급 시각 — 디버깅 및 보안 감사용
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'token': self.token,
            'expires_at': self.expires_at,
            'is_revoked': self.is_revoked,
            'created_at': self.created_at
        }
