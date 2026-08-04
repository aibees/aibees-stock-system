import OpenDartReader as dart


class KisFinService:
    ####################################################
    # __init__
    # - KisFinService init
    ####################################################
    def __init__(self):
        self.__name__ = 'KisFinService'

    def compute_fin_indicator(self, stock):
        pass

    def get_fin_indicator(self, code):
        api_key = 'da49127468e7c3c11f6fccd3feba4033406fefb5'
        dart_fn = dart(api_key)
        """
            OpenDartReader를 이용해 재무제표 주요 계정을 가져와 투자 적합성을 판별합니다.
            """
        try:
            # dart.finstate: 주요 재무계정과목 데이터 가져오기
            # '11011' = 사업보고서 (연간)
            fs = dart_fn.finstate(code, 2024, '11011')

            if fs is None or fs.empty:
                return {"종목": code, "최종결론": "데이터 없음"}

            # 계정명(account_nm)으로 금액(thstrm_amount: 당기금액)을 추출하는 헬퍼 함수
            def get_amount(account_name):
                row = fs.loc[fs['account_nm'] == account_name]
                if not row.empty:
                    val = row['thstrm_amount'].values[0]
                    # 금액이 문자열(콤마 포함)로 들어오므로 콤마 제거 후 float 변환
                    return float(val.replace(',', '')) if pd.notnull(val) and val != '' else 0.0
                return 0.0

            # --- 1. 주요 재무 항목 추출 ---
            current_assets = get_amount('유동자산')
            current_liabilities = get_amount('유동부채')
            total_liabilities = get_amount('부채총계')
            total_equity = get_amount('자본총계')
            revenue = get_amount('매출액')
            op_income = get_amount('영업이익')
            net_income = get_amount('당기순이익')

            # --- 2. 주요 지표 직접 계산 ---
            # 0 나누기 에러 방지를 위한 조건부 계산
            debt_ratio = (total_liabilities / total_equity * 100) if total_equity else 0
            current_ratio = (current_assets / current_liabilities * 100) if current_liabilities else 0
            op_margin = (op_income / revenue * 100) if revenue else 0
            roe = (net_income / total_equity * 100) if total_equity else 0

            # --- 3. 적합성 판별 기준 (Thresholds) ---
            criteria = {
                '안정성_부채비율(<=150%)': debt_ratio <= 150,
                '안정성_유동비율(>=100%)': current_ratio >= 100,
                '수익성_영업이익률(>=5%)': op_margin >= 5,
                '수익성_ROE(>=8%)': roe >= 8
            }

            # --- 4. 최종 적합성 결론 ---
            pass_count = sum(criteria.values())
            total_items = len(criteria)

            # 4개 지표 중 3개 이상 통과 시 '적합'으로 판정
            is_fit = "적합" if pass_count >= 3 else "부적합"

            return {
                'result': True,
                'code': code,
                'debt_ratio': round(debt_ratio, 1),
                'volaitiliy_ratio': round(current_ratio, 1),
                'revenue_ratio': round(op_margin, 1),
                'roe': round(roe, 1)
            }

        except Exception as e:
            return {"result": False, "error": str(e)}

