from app.domain.model.masterStock import MasterStock
from app.domain.model.masterThemeCode import MasterThemeCode
from app.domain.model.masterThemeGroup import MasterThemeGroup


class MasterThemeDao:
    def __init__(self):
        self.__name__ = 'MasterThemeDao'


    def save_theme_grp(self, session, data: list):
        if not data:
            return 0

        session.bulk_insert_mappings(MasterThemeGroup, data)
        return len(data)


    def clean_theme_group(self, session):
        session.query(MasterThemeGroup).delete()


    def save_stock_by_theme(self, session, data: list):
        if not data:
            return 0

        session.bulk_insert_mappings(MasterThemeCode, data)
        return len(data)

    def clean_stock_by_theme(self, session):
        session.query(MasterThemeCode).delete()