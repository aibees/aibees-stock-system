import os
import zipfile
import urllib.request
import pandas as pd

from app.batches.jobs.job import Job
from app.batches.services.stockService import StockService
from app.config.database import dbConn


class StockCodeMasterJob(Job):
    def __init__(self):
        super().__init__()
        self.job_name = "StockCodeMasterJob"
        self.target = ['kospi', 'kosdaq']
        self.nxt_target = ['nxt_kospi', 'nxt_kosdaq']
        self.static_path = os.path.join(os.path.dirname(__file__), '../../static/')
        self.mst_url = 'https://new.real.download.dws.co.kr/common/master/'
        self.stockServiceImpl = StockService()

    def get_name(self):
        return self.job_name

    ####################################################
    # 배치 시작
    ####################################################
    def run_batch(self, **kwargs):
        suc_cnt = 0

        # 기존 내용 전부 삭제
        self.stockServiceImpl.clean_stock_master(self.session)

        for t in self.target:
            dict_list = self.extract_data(f'{t}_code.mst', t)
            cnt = self.stockServiceImpl.update_stock_master(self.session, dict_list)
            suc_cnt += cnt

        for nxt in self.nxt_target:
            nxt_list = self.extract_data_nxt(f'{nxt}_code.mst', nxt)
            print(f'[{nxt}] nxt_list len: {len(nxt_list)}')
            self.stockServiceImpl.update_stock_nxt_flag(self.session, nxt_list)

        return {
            'status': 'success',
            'desc': '종목코드 마스터 갱신 완료',
            'batch_cnt': suc_cnt
        }


    """
    ZIP file download하고, unzip 하여 .mst 파일 get
    """
    def download_and_extract(self, zip_file):
        dest = f'{self.static_path}{zip_file}'

        if os.path.exists(dest):
            os.remove(dest)

        urllib.request.urlretrieve(self.mst_url + zip_file, dest)
        with zipfile.ZipFile(dest, 'r') as zip_ref:
            zip_ref.extractall(self.static_path)

    def extract_data_nxt(self, name, type):
        code_list = []
        self.download_and_extract(name + '.zip')
        file_name = self.static_path + name

        with open(file_name, mode='r', encoding='cp949') as f:
            for row in f:
                stock_code = row[0:6]
                code_list.append(stock_code)

        os.remove(file_name)
        os.remove(f'{file_name}.zip')

        return code_list

    """
    .mst 파일에서 row read -> list(dict)로 추출
    """
    def extract_data(self, name, stock_type) -> list:
        self.download_and_extract(name + '.zip')

        file_name = self.static_path + name
        tmp1_path = self.static_path + name + '1.tmp'
        tmp2_path = self.static_path + name + '2.tmp'

        if os.path.exists(tmp1_path):
            os.remove(tmp1_path)
            os.remove(tmp2_path)


        with open(file_name, mode='r', encoding='cp949') as f, \
                open(tmp1_path, mode='w', encoding='utf-8') as tmp1, \
                open(tmp2_path, mode='w', encoding='utf-8') as tmp2:
            for row in f:
                rf1 = row[0:len(row) - 228]
                rf1_1 = rf1[0:9].rstrip()
                rf1_2 = rf1[9:21].rstrip()
                rf1_3 = rf1[21:].strip()
                tmp1.write(rf1_1 + ',' + rf1_2 + ',' + rf1_3 + '\n')

                rf2 = row[-228:]
                tmp2.write(rf2)

            tmp1.close()
            tmp2.close()

        os.remove(file_name)
        os.remove(f'{file_name}.zip')

        part1_columns = ['stock_code', 'corp_code', 'stock_name']
        df1 = pd.read_csv(tmp1_path, header=None, names=part1_columns, encoding='utf-8')

        field_specs = [2, 1, 4, 4, 4,
                       1, 1, 1, 1, 1,
                       1, 1, 1, 1, 1,
                       1, 1, 1, 1, 1,
                       1, 1, 1, 1, 1,
                       1, 1, 1, 1, 1,
                       1, 9, 5, 5, 1,
                       1, 1, 2, 1, 1,
                       1, 2, 2, 2, 3,
                       1, 3, 12, 12, 8,
                       15, 21, 2, 7, 1,
                       1, 1, 1, 1, 9,
                       9, 9, 5, 9, 8,
                       9, 3, 1, 1, 1]

        part2_columns = ['group_code', 'market_capital', 'cls_first', 'cls_mid', 'cls_last',
                         '제조업', '저유동성', '지배구조지수종목', 'KOSPI200섹터업종', 'KOSPI100',
                         'KOSPI50', 'KRX', 'ETP', 'ELW발행', 'KRX100',
                         'KRX자동차', 'KRX반도체', 'KRX바이오', 'KRX은행', 'SPAC',
                         'KRX에너지화학', 'KRX철강', '단기과열', 'KRX미디어통신', 'KRX건설',
                         'Non1', 'KRX증권', 'KRX선박', 'KRX섹터_보험', 'KRX섹터_운송',
                         'SRI', '기준가', '매매수량단위', '시간외수량단위', 'market_stop',
                         '정리매매', '관리종목', '시장경고', '경고예고', '불성실공시',
                         '우회상장', '락구분', '액면변경', '증자구분', '증거금비율',
                         '신용가능', '신용기간', '전일거래량', '액면가', '상장일자',
                         '상장주수', '자본금', '결산월', '공모가', '우선주',
                         '공매도과열', '이상급등', 'KRX300', 'KOSPI', '매출액',
                         '영업이익', '경상이익', '당기순이익', 'ROE', '기준년월',
                         '시가총액', '그룹사코드', '회사신용한도초과', '담보대출가능', '대주가능'
                         ]

        df2 = pd.read_fwf(tmp2_path, widths=field_specs, names=part2_columns)
        df = pd.merge(df1, df2, how='outer', left_index=True, right_index=True)
        df['group_code'] = df['group_code'].fillna('')
        df['stock_type'] = stock_type.upper()
        df['stock_type_yf'] = 'KQ' if stock_type.upper() == 'KOSDAQ' else 'KS'

        if stock_type.upper() == 'KOSDAQ':
            df['group_code'] = 'ST'

        df = df[df['stock_code'].str.len() < 7]

        # delete tmp file
        os.remove(tmp1_path)
        os.remove(tmp2_path)

        return df[['corp_code', 'stock_code', 'stock_name', 'stock_type', 'stock_type_yf', 'group_code', 'market_stop']].to_dict('records')

