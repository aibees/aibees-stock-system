import requests
from datetime import datetime, timedelta

from app.config.db.database import dbConn
from app.utils.mariaEnv import MariaEnv
from app.services.kis.oauthService import KisAuthService
from app.domains.dao.masterHolidayDao import MasterHolidayDao
from app.domains.dao.masterStockDao import MasterStockDao

mariaEnv = MariaEnv()

class KisChartService:
    def __init__(self):
        self.session = dbConn.get_session()
        self.authService = KisAuthService()
        self.historyDao = MasterHolidayDao()
        self.stockDao = MasterStockDao()
    
    def getStockCodeList(self, param):
        resultArr = self.stockDao.select_master_stock(param);
        return list(map(lambda x:x['stock_code'], resultArr))
    
    def getDomesticDailyChart(self, param):
        url = mariaEnv.getKisDomain() + '/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice'
        h = {
            'Content-Type': 'application/json; charset=utf-8',
            'authorization': 'Bearer ' + self.authService.getOauth()['key_value'],
            'appkey': mariaEnv.getKisAppKey(),
            'appsecret': mariaEnv.getKisSecretKey(),
            'tr_id': 'FHKST03010100',
            'custtype': 'P'
        }
        param = {
            'FID_COND_MRKT_DIV_CODE': 'J',
            'FID_INPUT_ISCD': param['code'],
            'FID_INPUT_DATE_1': self.__getStartDate(param['endDate']),
            'FID_INPUT_DATE_2': param['endDate'],
            'FID_PERIOD_DIV_CODE': 'D',
            'FID_ORG_ADJ_PRC': '0',
        }
        
        print(param)
        
        response = requests.get(url, params=param, headers=h)
        
        resData = response.json()
        
        return resData
    
    def __getStartDate(self, endDate):
        limit = 80
        current = datetime.strptime(endDate, "%Y%m%d")
        yearBefore = (current - timedelta(days=240)).strftime("%Y%m%d")
        search_date = {
            'startDate': yearBefore,
            'endDate': endDate
        }
        holiday = self.historyDao.select_holiday_list(search_date)
        
        holi_date = list(map(lambda x:x['ymd'], holiday))
        
        while limit > 0 :
            if current.weekday() < 5 or current.strftime("%Y%m%d") not in holi_date:
                limit -= 1
            current -= timedelta(days=1)
        
        return current.strftime('%Y%m%d')