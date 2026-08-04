"""
공통 DAO 기반 클래스.

서브클래스에서 `model` 클래스 변수를 지정하면
아래 3가지 공통 메서드를 자동으로 사용할 수 있다.

  - select_all(session)          : 전체 목록 조회
  - update_by_key(session, data) : PK 기준 업데이트 (PK 외 모든 필드 갱신)
  - delete_by_key(session, data) : PK 기준 삭제

Example:
    class BatchJobMasterDao(BaseDao):
        model = BatchJobMaster

        def __init__(self):
            self.__name__ = 'BatchJobMasterDao'
"""

import logging

from sqlalchemy import delete, select, update

logging.basicConfig(level=logging.ERROR)


class BaseDao:
    model = None  # 서브클래스에서 반드시 지정

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------
    def _pk_names(self):
        """모델의 PK 컬럼 이름 목록을 반환한다."""
        return [col.name for col in self.model.__mapper__.primary_key]

    def _pk_where(self, data: dict):
        """data dict 에서 PK 값을 읽어 WHERE 절 조건 리스트를 반환한다."""
        return [getattr(self.model, pk) == data[pk] for pk in self._pk_names()]

    # ------------------------------------------------------------------
    # 공통 CRUD
    # ------------------------------------------------------------------
    def select_all(self, session) -> list:
        """테이블 전체 레코드를 조회한다."""
        stmt = select(self.model)
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]

    def update_by_key(self, session, data: dict) -> None:
        """
        PK 기준으로 레코드를 업데이트한다.
        data 딕셔너리에서 PK 컬럼은 WHERE 조건으로 사용되고,
        나머지 키-값이 SET 절에 반영된다.
        """
        pk_set = set(self._pk_names())
        values = {k: v for k, v in data.items() if k not in pk_set}
        if not values:
            return
        stmt = update(self.model).where(*self._pk_where(data)).values(**values)
        session.execute(stmt)

    def delete_by_key(self, session, data: dict) -> None:
        """PK 기준으로 레코드를 삭제한다."""
        stmt = delete(self.model).where(*self._pk_where(data))
        session.execute(stmt)
