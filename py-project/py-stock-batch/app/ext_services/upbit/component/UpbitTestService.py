
from app.domain.dao.userTestDao import UserTestDao


class UpbitTestService:

    def __init__(self):
        self.__name__ = 'UpbitTestService'
        self.userTestDaoImpl = UserTestDao()