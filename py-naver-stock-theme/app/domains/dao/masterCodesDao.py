from app.domains.models.masterCodes import MasterCodes
from sqlalchemy import select, update, and_, func

import logging

logging.basicConfig(level=logging.ERROR)

class MasterCodesDao:
    def __init__(self):
        self.__name__ = 'MasterCodesDao'

    # select list
    # ================================================================
    def select_master_code(self, session, param):

        stmt = select(
            MasterCodes
        ).where(
            and_(
                MasterCodes.system == param['system'],
                MasterCodes.source == param['source'],
                MasterCodes.category == param['category']
            )
        )
        results = session.execute(stmt).scalars().all()
        return [obj.to_dict() for obj in results]
