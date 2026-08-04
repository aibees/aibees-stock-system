import requests
from datetime import datetime

from app.config.db.database import dbConn
from app.domains.dao.masterInfoDao import MasterInfosDao
from app.utils.mariaEnv import MariaEnv

mariaEnv = MariaEnv()

class KisAuthService:
    def __init__(self):
        self.masterInfoDao = MasterInfosDao()
        self.session = dbConn.get_session()
        
    def getOauth(self):
        authType = "Bearer"
        
        keyData = self.masterInfoDao.select_master_key_by_type(authType)
        
        if len(keyData) == 0:
            return self.sendOauthReq()
        
        else :
            bearer = keyData[0]
            # expiring = datetime.strptime(bearer.expired_date, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            
            if bearer.expired_date < now : # 만료됨
                return self.sendOauthReq()
            else :
                return bearer.to_dict()
                
    # 실질적 Oauth 요청
    def sendOauthReq(self):
        try:
            kisInfo = mariaEnv.getKisKey()
            url = kisInfo['domain'] + '/oauth2/tokenP'
            h = {
                'Content-Type': 'application/json; charset=UTF-8'
            }
            data = {
                'grant_type': 'client_credentials',
                'appkey': mariaEnv.getKisAppKey(),
                'appsecret': mariaEnv.getKisSecretKey()
            }
            
            response = requests.post(url, json=data, headers=h)
            
            resData = response.json()
            
            respType = {
                'key_type': resData.get('token_type'),
                'key_value': resData.get('access_token'),
                'expired_date': resData.get('access_token_token_expired')
            }
            
            self.masterInfoDao.insert_master_key(self.session, respType)
            self.session.commit()
            return respType
        except Exception as e:
            print(str(e))
            self.session.rollback()
        
        
        
        