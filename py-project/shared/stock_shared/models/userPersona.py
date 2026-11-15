from sqlalchemy import Column, DateTime, Integer, String, func

from stock_shared.base import Base


class UserPersona(Base):
    """성향 테스트 결과(계정 저장) — 유저당 1행. 양봉상회 스키마에만 있다(sql/yangbong/002_service_tables.sql).

    양봉상회 API(router_user_options.py 의 /user-options/persona)만 쓴다. 비밀상회(`stock`)·워커·배치에는 없다.
    updated_at 은 기기 값과 계정 값 중 최근 것을 고르는 기준이라 API 서버가 직접 넣는다
    (DB NOW() 와 서버 시간대가 달라도 같은 서버가 쓰고 읽으므로 epoch 변환이 어긋나지 않는다).
    """

    __tablename__ = "user_persona"

    user_id = Column(Integer, primary_key=True, nullable=False)
    persona_type = Column(String(30), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now())

    def to_dict(self):
        return {
            "persona_type": self.persona_type,
            # 화면은 기기 저장 시각(ms)과 비교한다
            "updated_at": int(self.updated_at.timestamp() * 1000) if self.updated_at else None,
        }
