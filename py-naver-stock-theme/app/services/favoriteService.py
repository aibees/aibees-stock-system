from app.domains.dao.favoriteGroupDao import FavoriteGroupDao

class FavoriteService:
    def __init__(self):
        self.name = 'FavoriteService'
        self.favoriteDao = FavoriteGroupDao()
    
    def selectUserGroups(self, session, param):
        return self.favoriteDao.select_favorite_user_group(session, param)
    
    def processUserGroups(self, session, param):
        result = None
        
        if param['types'] == 'INSERT':
            result = None