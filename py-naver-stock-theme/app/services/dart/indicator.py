import requests
import pandas as pd

class dartIndicator:
    def __init__(self) :
        self.api_key = 'da49127468e7c3c11f6fccd3feba4033406fefb5'
        
    def get_indicator(self, corp_code):
        

        url = 'https://kind.krx.co.kr/corpgeneral/corpList.do?method=download'
        df = pd.read_html(url, header=0)[0]
        df['종목코드'] = df['종목코드'].apply(lambda x: f'{x:06d}')
        print(df)
        # url = f"https://opendart.fss.or.kr/api/fnlttSinglAcnt.json?crtfc_key={self.api_key}&corp_code={corp_code}&bsns_year=2025&reprt_code=11013"
        # res = requests.get(url)
        # data = res.json()
        
        # for item in data['list']:
        #     if item['fs_nm'] == '재무제표':
        #         print(item)
                
                
    # https://opendart.fss.or.kr/api/corpCode.xml?auth=da49127468e7c3c11f6fccd3feba4033406fefb5