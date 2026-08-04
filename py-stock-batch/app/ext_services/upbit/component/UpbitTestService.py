
from app.domain.dao.UserTestDao import UserTestDao


class UpbitTestService:

    def __init__(self):
        self.__name__ = 'UpbitTestService'
        self.userTestDaoImpl = UserTestDao()