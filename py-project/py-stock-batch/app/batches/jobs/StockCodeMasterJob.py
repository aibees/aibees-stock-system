import os
import time
import zipfile
import urllib.request
import pandas as pd

from app.batches.jobs.job import Job
from app.batches.services.stockService import StockService
from app.ext_services.kis.KisEngine import KisEngine
from app.ext_services.kis.keyLoader import list_kis_user_ids
from stock_shared.dao.masterStockDao import MasterStockDao
from stock_shared.db.database import dbConn

# ──────────────────────────────────────────────────────────────────────
# KSIC(표준산업분류) 대분류(2자리) → KRX 지수업종 이름 (중분류명, 대분류명)
#   .mst 에 업종이 '0000' 인 현물만 이걸로 채운다(KOSDAQ IT·SW·게임 등 — KOSDAQ 'IT 서비스'·'통신'
#   소속 종목이 .mst 에 하나도 없다). 대응은 2026-10-12 분류된 종목 469개의 KSIC 와 .mst 업종을 대조해 정했다
#   (예: 26·28 → 전기·전자, 27 → 의료·정밀기기, 59·60·90·91 → 오락·문화, 64 → 금융, 65 → 보험).
#   이름으로 시장별 코드(KOSPI 00xx / KOSDAQ 10xx)를 찾고, 그 시장에 없는 중분류면 대분류만,
#   대분류도 없으면 업종 없음(화면 '미분류'). 예) KOSPI 엔 '기타제조'가 없어 '제조'만 / KOSDAQ 엔 '부동산'이 없어 미분류.
#   58(출판업)은 3자리로 나눈다 — 582 소프트웨어 개발·공급 → IT 서비스, 581 서적·잡지 → 오락·문화.
#   66(금융·보험 서비스)은 증권/금융이 섞여(표본 12:10) 상위 '금융'으로 둔다.
# ──────────────────────────────────────────────────────────────────────
_MFG = '제조'
_KSIC_DIV_TO_KRX = {
    **{d: ('음식료·담배', _MFG) for d in ('10', '11', '12')},
    **{d: ('섬유·의류', _MFG) for d in ('13', '14', '15')},
    **{d: ('종이·목재', _MFG) for d in ('16', '17')},
    '18': ('출판·매체복제', _MFG),
    **{d: ('화학', _MFG) for d in ('19', '20', '22')},
    '21': ('제약', _MFG),
    '23': ('비금속', _MFG),
    **{d: ('금속', _MFG) for d in ('24', '25')},
    **{d: ('전기·전자', _MFG) for d in ('26', '28')},
    '27': ('의료·정밀기기', _MFG),
    '29': ('기계·장비', _MFG),
    **{d: ('운송장비·부품', _MFG) for d in ('30', '31')},
    **{d: ('기타제조', _MFG) for d in ('32', '33', '34')},
    **{d: (None, '전기·가스') for d in ('35', '36')},
    **{d: (None, '건설') for d in ('41', '42')},
    **{d: (None, '유통') for d in ('45', '46', '47')},
    **{d: (None, '운송·창고') for d in ('49', '50', '51', '52')},
    **{d: (None, 'IT 서비스') for d in ('62', '63')},
    '61': (None, '통신'),
    **{d: (None, '오락·문화') for d in ('59', '60', '90', '91')},
    '64': (None, '금융'),
    '65': ('보험', '금융'),
    '66': (None, '금융'),
    '68': (None, '부동산'),
    **{d: (None, '일반서비스') for d in ('55', '56', '70', '71', '72', '73', '74', '75', '76',
                                    '85', '86', '87', '94', '95', '96')},
}
KSIC_CALL_INTERVAL_SEC = 0.12   # StockInvestorJob 과 같은 여유(같은 앱키를 trade worker 도 쓴다)


class StockCodeMasterJob(Job):
    def __init__(self):
        super().__init__()
        self.job_name = "StockCodeMasterJob"
        self.target = ['kospi', 'kosdaq']
        self.nxt_target = ['nxt_kospi', 'nxt_kosdaq']
        self.static_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', 'static')
        ) + os.sep
        # 컨테이너/신규 환경에서 static 디렉터리가 없으면 다운로드가 FileNotFoundError 로 실패한다.
        os.makedirs(self.static_path, exist_ok=True)
        self.mst_url = 'https://new.real.download.dws.co.kr/common/master/'
        self.stockServiceImpl = StockService()
        self.masterStockDaoImpl = MasterStockDao()
        self.idx_bztp_names = {}

    def get_name(self):
        return self.job_name

    ####################################################
    # 배치 시작
    ####################################################
    def run_batch(self, **kwargs):
        suc_cnt = 0

        # 지수업종 코드→이름 (종목 다운로드 전에 받아야 삭제 후 실패로 마스터가 비는 일이 없다)
        self.idx_bztp_names = self.extract_idx_bztp_names('idxcode.mst')

        # 종목 파일을 전부 읽고 KSIC 보충까지 끝낸 뒤에 지운다(중간 실패로 마스터가 비지 않게).
        # 이미 받아 둔 KSIC 는 삭제 전에 챙겨서 같은 종목은 다시 호출하지 않는다.
        ksic_cache = self.masterStockDaoImpl.select_std_idst_map(self.session)
        all_rows = []
        for t in self.target:
            all_rows.extend(self.extract_data(f'{t}_code.mst', t))
        ksic_stat = self.fill_idx_bztp_by_ksic(all_rows, ksic_cache)

        # 기존 내용 전부 삭제
        self.stockServiceImpl.clean_stock_master(self.session)
        suc_cnt += self.stockServiceImpl.update_stock_master(self.session, all_rows)

        for nxt in self.nxt_target:
            nxt_list = self.extract_data_nxt(f'{nxt}_code.mst', nxt)
            print(f'[{nxt}] nxt_list len: {len(nxt_list)}')
            self.stockServiceImpl.update_stock_nxt_flag(self.session, nxt_list)

        return {
            'status': 'SUCCESS',
            'desc': f'종목코드 마스터 갱신 완료 (업종 KSIC 보충 {ksic_stat})',
            'batch_cnt': suc_cnt
        }

    ####################################################
    # .mst 에 업종이 없는 현물 → KSIC 로 KRX 업종 채우기
    ####################################################
    def fill_idx_bztp_by_ksic(self, rows: list, ksic_cache: dict) -> str:
        """rows 를 제자리에서 고친다. 반환은 결과 요약 문자열(배치 이력 desc 용).
        KIS 호출이 안 되면(키 없음 등) 보충만 건너뛰고 마스터 적재는 그대로 진행한다."""
        targets = [r for r in rows if r['group_code'] == 'ST' and not r['idx_bztp_lcls_cd']]
        misses = [r['stock_code'] for r in targets if r['stock_code'] not in ksic_cache]

        called = 0
        if misses:
            try:
                uids = list_kis_user_ids()
                engine = KisEngine(user_id=uids[0]) if uids else KisEngine()
            except Exception as e:
                print(f'[{self.job_name}] KIS 엔진 생성 실패 → KSIC 신규 조회 생략: {e}', flush=True)
                engine = None
            if engine:
                for code in misses:
                    got = engine.get_std_industry(code)
                    called += 1
                    if got:
                        ksic_cache[code] = got
                    time.sleep(KSIC_CALL_INTERVAL_SEC)

        mapped = 0
        for r in targets:
            ksic = ksic_cache.get(r['stock_code'])
            if not ksic:
                continue
            r['std_idst_clsf_cd'], r['std_idst_clsf_name'] = ksic
            market = '1' if r['stock_type'] == 'KOSDAQ' else '0'
            lcls, mcls = self.ksic_to_idx_bztp(ksic[0], market)
            if lcls:
                r['idx_bztp_src'] = 'KSIC'
                r['idx_bztp_lcls_cd'], r['idx_bztp_lcls_name'] = lcls, self.idx_bztp_names.get(lcls)
                if mcls:
                    r['idx_bztp_mcls_cd'], r['idx_bztp_mcls_name'] = mcls, self.idx_bztp_names.get(mcls)
                mapped += 1

        stat = f'대상 {len(targets)} · 신규조회 {called} · 매핑 {mapped} · 미분류 {len(targets) - mapped}'
        print(f'[{self.job_name}] 업종 KSIC 보충: {stat}', flush=True)
        return stat

    def ksic_to_idx_bztp(self, ksic_cd: str, market: str):
        """KIS std_idst_clsf_cd(예 '105802' = 섹션 2자리 + KSIC 대분류 2자리 + 중분류 2자리)
        → (대분류코드, 중분류코드) in 해당 시장(market '0' KOSPI / '1' KOSDAQ). 없으면 (None, None)."""
        div = ksic_cd[2:4] if len(ksic_cd) >= 4 else ''
        if div == '58':
            mapping = (None, 'IT 서비스') if ksic_cd[4:6] == '02' else (None, '오락·문화')
        else:
            mapping = _KSIC_DIV_TO_KRX.get(div)
        if not mapping:
            return None, None

        by_name = {name: code for code, name in self.idx_bztp_names.items() if code[0] == market}
        mcls_name, lcls_name = mapping
        lcls = by_name.get(lcls_name)
        if not lcls:
            return None, None
        return lcls, by_name.get(mcls_name) if mcls_name else None


    """
    ZIP file download하고, unzip 하여 .mst 파일 get
    """
    def download_and_extract(self, zip_file):
        # 인스턴스가 재사용되거나 디렉터리가 중간에 사라진 경우를 대비해 매번 보장
        os.makedirs(self.static_path, exist_ok=True)
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
    업종코드 마스터(idxcode.mst) → {4자리 업종코드: 업종명}.
    행 = 1자리 구분(0 KOSPI, 1 KOSDAQ, 2 KOSPI200 …) + 4자리 코드 + 업종명. 예) '00027제조', '11015오락·문화'.
    종목 .mst 의 지수업종 대/중/소분류는 앞 1자리를 뺀 4자리라 그대로 키로 쓴다(KOSPI 00xx / KOSDAQ 10xx 라 겹치지 않음).
    """
    def extract_idx_bztp_names(self, name) -> dict:
        self.download_and_extract(name + '.zip')
        file_name = self.static_path + name

        names = {}
        with open(file_name, mode='r', encoding='cp949') as f:
            for row in f:
                code, bztp_name = row[1:5], row[5:].strip()
                if code.isdigit() and bztp_name:
                    names.setdefault(code, bztp_name)

        os.remove(file_name)
        os.remove(f'{file_name}.zip')
        return names

    # KOSDAQ 종목마스터(kosdaq_code.mst) 뒷부분 221자 레이아웃.
    #   KOSPI 와 앞쪽 지수·섹터 플래그 개수가 달라 이후 필드 위치가 전부 다르다. 기준가 이후 필드명은
    #   KOSPI 와 같게 맞춰(market_stop=거래정지, 정리매매, 관리종목, 상장주수 …) 아래 공통 처리를 그대로 탄다.
    #   검증(2026-10-11): 상장일자(알테오젠 20141212), 상장주수(에코프로비엠 97,830천주 = KIS 97,830,434주),
    #   관리종목 Y/N 6종목 표본이 KIS 현재가 API(mang_issu_cls_code)와 일치.
    #   앞쪽 플래그(flag01~21)는 쓰지 않아 이름을 붙이지 않았다.
    #   ※ 2026-10-12 전까지 222자(플래그 22개)로 읽어 앞쪽 필드가 한 칸 밀렸다(group_code ' S', 업종 '1101'…).
    #     기준가 이후는 플래그 개수 차이로 상쇄돼 그대로였다(전 1,825행 대조). 업종 분류를 쓰면서 바로잡음.
    KOSDAQ_FIELD_SPECS = ([2, 1, 4, 4, 4] + [1] * 21 +
                          [9, 5, 5, 1, 1, 1, 2, 1, 1, 1, 2, 2, 2, 3, 1, 3, 12, 12, 8, 15, 21, 2, 7,
                           1, 1, 1, 1, 9, 9, 9, 5, 9, 8, 9, 3, 1, 1, 1])
    KOSDAQ_PART2_COLUMNS = (['group_code', 'market_capital', 'cls_first', 'cls_mid', 'cls_last'] +
                            [f'flag{i:02d}' for i in range(1, 22)] +
                            ['기준가', '매매수량단위', '시간외수량단위', 'market_stop', '정리매매',
                             '관리종목', '시장경고', '경고예고', '불성실공시', '우회상장',
                             '락구분', '액면변경', '증자구분', '증거금비율', '신용가능',
                             '신용기간', '전일거래량', '액면가', '상장일자', '상장주수',
                             '자본금', '결산월', '공모가', '우선주', '공매도과열',
                             '이상급등', 'KRX300', '매출액', '영업이익', '경상이익',
                             '당기순이익', 'ROE', '기준년월', '시가총액', '그룹사코드',
                             '회사신용한도초과', '담보대출가능', '대주가능'])

    """
    .mst 파일에서 row read -> list(dict)로 추출
    """
    def extract_data(self, name, stock_type) -> list:
        self.download_and_extract(name + '.zip')

        file_name = self.static_path + name
        is_kosdaq = stock_type.upper() == 'KOSDAQ'
        # 행 뒷부분(고정폭 필드) 길이 = 데이터 + 줄바꿈 1자. KOSPI 227+1 / KOSDAQ 221+1.
        #   ※ 2026-10-11 전까지 KOSDAQ 도 KOSPI 길이·필드로 읽어서 KOSDAQ 의 거래정지/정리매매/관리종목이
        #     한 칸씩 밀려 저장됐다(market_stop 이 전부 '1', 거래정지가 trading_halt 로, 정리매매가 admin_issue 로).
        tail_len = 222 if is_kosdaq else 228
        tmp1_path = self.static_path + name + '1.tmp'
        tmp2_path = self.static_path + name + '2.tmp'

        if os.path.exists(tmp1_path):
            os.remove(tmp1_path)
            os.remove(tmp2_path)


        with open(file_name, mode='r', encoding='cp949') as f, \
                open(tmp1_path, mode='w', encoding='utf-8') as tmp1, \
                open(tmp2_path, mode='w', encoding='utf-8') as tmp2:
            for row in f:
                rf1 = row[0:len(row) - tail_len]
                rf1_1 = rf1[0:9].rstrip()
                rf1_2 = rf1[9:21].rstrip()
                rf1_3 = rf1[21:].strip()
                tmp1.write(rf1_1 + ',' + rf1_2 + ',' + rf1_3 + '\n')

                rf2 = row[-tail_len:]
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

        if is_kosdaq:
            field_specs, part2_columns = self.KOSDAQ_FIELD_SPECS, self.KOSDAQ_PART2_COLUMNS
        # 업종 분류코드는 '0027' 처럼 앞자리 0 이 있어 문자열로 읽는다.
        df2 = pd.read_fwf(tmp2_path, widths=field_specs, names=part2_columns,
                          dtype={'cls_first': str, 'cls_mid': str, 'cls_last': str})
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

        # 관리종목/정리매매 는 이미 .mst 파일에 있는 'Y'/'N' 플래그를 그대로 저장한다
        # (2026-09 세션: 매수추천이 관리종목에 쏠리는 문제 확인 → 별도 API 호출 없이
        # 여기서 같이 채워서 StockBuyCheckJob 이 안정성 필터로 바로 쓸 수 있게 함).
        df['admin_issue'] = df['관리종목']
        df['trading_halt'] = df['정리매매']

        # 상장주식수(주) — .mst '상장주수'는 천주 단위라 ×1000. 종목 화면 시가총액 계산용
        #   (시가총액 = 상장주식수 × 직전 영업일 종가, API 에서 계산). 값이 없으면 NULL.
        #   ※ .mst 의 '시가총액'/'기준가'는 하루 늦게 갱신되는 경우가 있어 쓰지 않는다.
        shares = pd.to_numeric(df['상장주수'], errors='coerce')
        df['listed_shares'] = [int(v) * 1000 if pd.notna(v) and v > 0 else None for v in shares]

        # 지수업종 대/중/소분류. '0000'·빈값은 NULL — 현물이면 run_batch 가 KSIC 로 보충한다.
        names = self.idx_bztp_names
        for src, dst in (('cls_first', 'lcls'), ('cls_mid', 'mcls'), ('cls_last', 'scls')):
            codes = [c if isinstance(c, str) and c.isdigit() and c != '0000' else None for c in df[src]]
            df[f'idx_bztp_{dst}_cd'] = codes
            df[f'idx_bztp_{dst}_name'] = [names.get(c) if c else None for c in codes]
        df['idx_bztp_src'] = ['MST' if c else None for c in df['idx_bztp_lcls_cd']]
        df['std_idst_clsf_cd'] = None
        df['std_idst_clsf_name'] = None

        return df[['corp_code', 'stock_code', 'stock_name', 'stock_type', 'stock_type_yf',
                   'group_code', 'market_stop', 'admin_issue', 'trading_halt',
                   'listed_shares',
                   'idx_bztp_lcls_cd', 'idx_bztp_lcls_name',
                   'idx_bztp_mcls_cd', 'idx_bztp_mcls_name',
                   'idx_bztp_scls_cd', 'idx_bztp_scls_name',
                   'idx_bztp_src', 'std_idst_clsf_cd', 'std_idst_clsf_name']].to_dict('records')

