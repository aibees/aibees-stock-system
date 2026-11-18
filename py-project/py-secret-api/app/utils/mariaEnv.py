from dotenv import load_dotenv
import os

class MariaEnv:
    def __init__(self):
        load_dotenv()
        self.KIS_DOMAIN=os.getenv("KIS_DOMAIN")
        self.KIS_APP_KEY=os.getenv("KIS_APP_KEY")
        self.KIS_SECRET_KEY=os.getenv("KIS_SECRET_KEY")
        self.API_DATA_KEY=os.getenv("API_DATA_KEY")
        
    def getKisKey(self):
        return {
            'domain': self.KIS_DOMAIN,
            'appKey': self.KIS_APP_KEY,
            'secretKey': self.KIS_SECRET_KEY
        }
        
    def getKisAppKey(self):
        return self.KIS_APP_KEY
    
    def getKisSecretKey(self):
        return self.KIS_SECRET_KEY
    
    def getKisDomain(self):
        return self.KIS_DOMAIN
    
    def getApiDataKey(self):
        return self.API_DATA_KEY
        