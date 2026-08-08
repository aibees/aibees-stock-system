from stock_shared.dao.masterStockDao import MasterStockDao
from stock_shared.dao.tradeBuyTargetStockDao import TradeBuyTargetStockDao
from app.domain.dao.tradeSellTargetStockDao import TradeSellTargetStockDao
from stock_shared.dao.stockSellRequestDao import StockSellRequestDao


class StockService:
    def __init__(self):
        self.__name__ = "StockService"
        self.stockMasterDaoImpl = MasterStockDao()
        self.tradeBuyTargetStockDaoImpl = TradeBuyTargetStockDao()
        self.tradeSellTargetStockDaoImpl = TradeSellTargetStockDao()
        self.stockSellRequestDaoImpl = StockSellRequestDao()

    def get_stock_master_list(self, session, search_type: str) -> list:

        param = {}

        if search_type == 'batches':
            param = {
                'in_market_stop': ['1', 'N'],
                'in_group_code': ['ST', 'RT', 'MF'] # 일반, 리츠, 투자회사
            }

        return self.stockMasterDaoImpl.select_stock_list(session, param)

    def clean_stock_master(self, session):
        self.stockMasterDaoImpl.clean_stock_list_all(session)

    def update_stock_master(self, session, data: list) -> int:
        return self.stockMasterDaoImpl.update_stock_list(session, data)

    def update_stock_nxt_flag(self, session, data: list) -> None:
        self.stockMasterDaoImpl.update_stock_nxt_flag(session, data)

    def get_buy_target_stock_list(self, session, param:dict) -> list:
        target = self.tradeBuyTargetStockDaoImpl.select_stock_master_list(session, param)

        def form_trade_data(data: dict) -> dict:
            return {
                'stock_code': data['stock_code'],
                'stock_name': data['stock_name'],
                'action_type': data['action_type'],
                'todayStock': {
                    'open': data['open'],
                    'high': data['high'],
                    'low': data['low'],
                    'close': data['close'],
                    'volume': data['volume'],
                    'rate': data['rate'],
                },
                'indicator': {
                    'macd_cross': data['macd_cross'],
                    'obv_cross': data['obv_cross'],
                    'is_vol_limit': data['is_vol_limit'],
                    'is_under_bb_upper': data['is_under_bb_upper'],
                    'is_over_on_mid': data['is_over_on_mid'],
                    'is_vol_surge': data['is_vol_surge'],
                    'is_bb_mid_breakout': data['is_bb_mid_breakout'],
                },
                'fin': {
                    'eps': data['eps'],
                    'per': data['per'],
                    'pbr': data['pbr'],
                    'roe': data['roe'],
                    'peg': data['peg'],
                }
            }
        return [form_trade_data(t) for t in target]

    def clean_buy_target_stock_by_ymd(self, session, ymd: str) -> int:
        return self.tradeBuyTargetStockDaoImpl.delete_by_ymd(session, ymd)

    def save_buy_target_stock_one(self, session, data: dict) -> None:
        self.tradeBuyTargetStockDaoImpl.upsert_trade_buy_target_stock(session, [data])

    def save_buy_target_stock_log(self, session, data:list) -> None:
        self.tradeBuyTargetStockDaoImpl.upsert_trade_buy_target_stock(session, data)

    def save_buy_target_stocks_bulk(self, session, data: list) -> None:
        """랭킹(score/rank_no)까지 포함된 매수타겟 전체를 한 번에 upsert.
        병렬 배치에서 스레드는 조회/계산만 하고, 메인 스레드가 랭크 산정 후 이 메서드로 일괄 저장한다."""
        self.tradeBuyTargetStockDaoImpl.upsert_trade_buy_target_stock(session, data)

    def update_buy_target_rank(self, session, data: dict) -> None:
        """단일 종목의 종합점수/순위만 갱신 (배치 종료 후 순위 패스용)"""
        self.tradeBuyTargetStockDaoImpl.update_rank(
            session, data['ymd'], data['stock_code'], data['score'], data['rank_no']
        )

    # ──────────────────────────────────────────────────────────────────
    # 종합 적합도 점수 & 순위 (기술 50% + 재무 30% + 유동성 20%)
    #  - result_list 의 각 dict 에 'score'(0~100), 'rank_no'(1=최상위) 를 주입
    #  - 순위는 그날 후보 전체를 비교하는 단면 연산이므로 배치 루프 종료 후 1회 수행
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def _to_float(v):
        try:
            if v is None:
                return None
            s = str(v).replace('%', '').replace(',', '').strip()
            if s in ('', '-', 'N/A'):
                return None
            return float(s)
        except (ValueError, TypeError):
            return None

    # ── 대조군 분석 반영 (2026-08-08, WIN 34건 vs CONTROL 470건 비교) ──────────
    # 근거: 매수추천_성공패턴_대조군분석.xlsx.
    #  · macd_cross='G'(신선한 골든크로스) 비율은 WIN 44.1% < CONTROL 65.3% — 오히려 역상관.
    #    → 스코어 기준을 raw 골든크로스에서 'macd_slope_up'(기울기 상승)으로 바꾸고 비중을 낮춘다.
    #  · is_vol_limit='Y' 는 WIN 34건 전원(100%) 충족 → 비중 상향.
    #  · ATR/종가(atr_ratio, 변동성): WIN 평균 11.8% vs CONTROL 8.9% — 가장 유의한 차이 → 신규 가점.
    #  · 고점 대비 눌림(dip_from_high): WIN -19.3% vs CONTROL -12.1% → 신규 가점(깊이 눌릴수록 유리).
    _ATR_RATIO_LO, _ATR_RATIO_HI = 0.05, 0.12          # kospi1.atr_ratio_min ~ atr_ratio_full_score 와 동일 구간
    _DIP_LO_PCT, _DIP_HI_PCT = 0.03, 0.15              # kospi1.dip_from_high_min_pct ~ full_pct 와 동일 구간

    def _tech_score(self, ind: dict) -> float:
        # MACD: 'macd_slope_up'(기울기 상승) 우선 사용. 구버전/DB 재구성 등으로 이 키가
        # 없는 indicator dict 가 들어오면 raw 골든크로스로 폴백한다.
        macd_slope_up = ind.get('macd_slope_up')
        if macd_slope_up is None:
            macd_slope_up = 'Y' if ind.get('macd_cross') == 'G' else 'N'
        macd = 1.0 if macd_slope_up == 'Y' else 0.4

        bb = 1.0 if ind.get('is_bb_mid_breakout') == 'Y' else 0.0
        vl = 1.0 if ind.get('is_vol_limit') == 'Y' else 0.0

        atr_ratio = self._to_float(ind.get('atr_ratio'))
        if atr_ratio is None:
            atr = 0.0
        elif atr_ratio <= self._ATR_RATIO_LO:
            atr = 0.0
        elif atr_ratio >= self._ATR_RATIO_HI:
            atr = 1.0
        else:
            atr = (atr_ratio - self._ATR_RATIO_LO) / (self._ATR_RATIO_HI - self._ATR_RATIO_LO)

        dip = self._to_float(ind.get('dip_from_high'))  # 0 이하(음수), 예: -0.193
        if dip is None:
            dip_score = 0.0
        else:
            d = abs(dip)
            if d <= self._DIP_LO_PCT:
                dip_score = 0.0
            elif d >= self._DIP_HI_PCT:
                dip_score = 1.0
            else:
                dip_score = (d - self._DIP_LO_PCT) / (self._DIP_HI_PCT - self._DIP_LO_PCT)

        # 가중치: macd 0.30 · bb중심선돌파 0.15 · 거래량하한 0.20 · 변동성(ATR) 0.20 · 눌림목 0.15
        return 0.30 * macd + 0.15 * bb + 0.20 * vl + 0.20 * atr + 0.15 * dip_score

    def _fund_score(self, fin: dict) -> float:
        eps = self._to_float(fin.get('eps'))
        per = self._to_float(fin.get('per'))
        pbr = self._to_float(fin.get('pbr'))
        roe = self._to_float(fin.get('roe'))
        peg = self._to_float(fin.get('peg'))

        prof = (eps is not None and eps > 0)
        eps_s = 1.0 if prof else 0.0
        # PER: 적자/None 0점, 0~10 우량, ~20 보통
        if not prof or per is None:
            per_s = 0.0
        elif 0 < per <= 10:
            per_s = 1.0
        elif per <= 20:
            per_s = 0.5
        else:
            per_s = 0.0
        # PBR
        if pbr is None:
            pbr_s = 0.0
        elif pbr <= 1.0:
            pbr_s = 1.0
        elif pbr <= 2.0:
            pbr_s = 0.5
        else:
            pbr_s = 0.0
        # ROE: 분수(0.14=14%) 가정, 혹시 %로 들어오면 보정
        if roe is None:
            roe_s = 0.0
        else:
            if abs(roe) > 1.5:
                roe = roe / 100.0
            roe_s = 1.0 if roe >= 0.12 else (0.5 if roe >= 0.05 else 0.0)
        # PEG: 적자 0점, 0이하(데이터없음) 중립, 0~1 우량
        if not prof:
            peg_s = 0.0
        elif peg is None or peg <= 0:
            peg_s = 0.5
        elif peg <= 1:
            peg_s = 1.0
        else:
            peg_s = 0.5
        return (eps_s + per_s + pbr_s + roe_s + peg_s) / 5.0

    @staticmethod
    def _parse_rate(r) -> float:
        """todayStock.rate('12.5%') → 12.5. 파싱 실패/None → +inf(후순위).
        과열최저 정렬(오름차순)에서 rate 낮은(안 오른) 종목이 상위."""
        raw = (r.get('todayStock') or {}).get('rate')
        try:
            return float(str(raw).replace('%', '').strip())
        except (ValueError, TypeError, AttributeError):
            return float('inf')

    def assign_ranks(self, result_list: list) -> list:
        """result_list 각 항목에 score/rank_no 주입 후 반환.
        rank_no = **과열최저(rate 오름차순)** 기준 (worker get_buy_targets 와 동일 기준).
        동률(rate 같음)이면 score 내림차순으로 타이브레이크. score 는 참고용으로 계속 계산."""
        import math
        if not result_list:
            return result_list

        # 유동성: 거래대금(close*volume) log 정규화
        turns = []
        for r in result_list:
            t = r.get('todayStock', {})
            close = self._to_float(t.get('close')) or 0.0
            vol = self._to_float(t.get('volume')) or 0.0
            turns.append(max(close * vol, 1.0))  # log 안정화 위해 하한 1
        logs = [math.log10(x) for x in turns]
        lo, hi = min(logs), max(logs)
        span = (hi - lo) if hi > lo else 0.0

        for i, r in enumerate(result_list):
            tech = self._tech_score(r.get('indicator', {}))
            fund = self._fund_score(r.get('fin', {}))
            liq = ((logs[i] - lo) / span) if span > 0 else 1.0  # 단일/동일 시 만점
            score = 100.0 * (0.5 * tech + 0.3 * fund + 0.2 * liq)
            r['score'] = round(score, 2)

        # 과열최저(rate 오름차순) → rank_no. 동률이면 score 내림차순.
        ranked = sorted(result_list, key=lambda x: (self._parse_rate(x), -x.get('score', 0.0)))
        for idx, r in enumerate(ranked, start=1):
            r['rank_no'] = idx
        return ranked

    # ──────────────────────────────────────────────────────────────────
    # stock_sell_request (Vue 입력 테이블) 관련 메서드
    # ──────────────────────────────────────────────────────────────────
    def get_sell_request_list(self, session, user_id: int) -> list:
        """user_id 기준 enabled_flag='Y'인 매도 체크 희망 종목 조회 (배치 입력)"""
        return self.stockSellRequestDaoImpl.select_enabled_list(session, user_id)

    def get_sell_request_all(self, session) -> list:
        """전체 목록 조회 (Vue 관리 화면용)"""
        return self.stockSellRequestDaoImpl.select_all(session)

    def save_sell_request(self, session, data: dict) -> None:
        """Vue에서 종목 등록/수정"""
        self.stockSellRequestDaoImpl.upsert(session, data)

    def toggle_sell_request(self, session, user_id: int, stock_code: str, enabled_flag: str) -> None:
        """Vue에서 활성화/비활성화 토글"""
        self.stockSellRequestDaoImpl.update_enabled_flag(session, user_id, stock_code, enabled_flag)

    # ──────────────────────────────────────────────────────────────────
    # trade_sell_target_stock (배치 결과 테이블) 관련 메서드
    # ──────────────────────────────────────────────────────────────────
    def get_sell_target_by_code(self, session, user_id: int, stock_code: str) -> dict | None:
        """복합 PK(user_id + stock_code) 기준 포지션 추적값 조회"""
        return self.tradeSellTargetStockDaoImpl.select_by_user_and_code(session, user_id, stock_code)

    def upsert_sell_check_result(self, session, data: dict) -> None:
        """배치 체크 결과 upsert (신규면 INSERT, 기존이면 추적값+판단 UPDATE)"""
        self.tradeSellTargetStockDaoImpl.upsert_check_result(session, data)

    def mark_sell_target_as_sold(self, session, user_id: int, stock_code: str) -> None:
        """매도 체결 완료 후 status='sold' 처리"""
        self.tradeSellTargetStockDaoImpl.update_status(session, user_id, stock_code, 'sold')

    def create_sell_mail_html(self, stocks_data: list) -> str:
        """매도 시그널 종목 이메일 HTML 생성"""
        html = """
        <div style="background-color: #f4f5f7; padding: 20px 10px; font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;">
            <div style="max-width: 400px; margin: 0 auto;">
                <h2 style="text-align: center; color: #333; margin-bottom: 20px;">📉 매도 시그널 감지</h2>
        """

        if not stocks_data:
            html += """
                <div style="background-color: #ffffff; padding: 30px 20px; border-radius: 12px; text-align: center; color: #666;">
                    매도 시그널 종목이 없습니다.
                </div>
            """
        else:
            action_label = {
                'SELL_STOP_LOSS': '🛑 손절',
                'SELL_PROFIT':    '✅ 익절',
                'SELL_TRAIL':     '📊 트레일링 스탑',
                'SELL_TIME':      '⏱ 타임스탑',
            }
            for stock in stocks_data:
                code        = stock.get('stock_code', '')
                name        = stock.get('stock_name', '')
                action      = stock.get('action_type', '')
                sell_ctx    = stock.get('sell_ctx', {})
                today_stock = stock.get('todayStock', {})

                label    = action_label.get(action, action)
                profit   = sell_ctx.get('profit_pct', '-')
                entry    = sell_ctx.get('entry_price', '-')
                stop_p   = sell_ctx.get('stop_price', '-')
                target_p = sell_ctx.get('target_price', '-')
                bars     = sell_ctx.get('bars_held', '-')
                curr_c   = today_stock.get('close', '-')

                profit_color = '#e22926' if str(profit).startswith('-') is False and profit != '-' else '#2679ed'

                html += f"""
                <div style="background-color: #ffffff; border-radius: 12px; padding: 16px; margin-bottom: 16px; box-shadow: 0 2px 5px rgba(0,0,0,0.08);">
                    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 10px;">
                        <tr>
                            <td style="font-size: 17px; font-weight: bold; color: #111;">{name} [{code}]</td>
                            <td align="right">
                                <span style="background-color: #e55; color: #fff; padding: 4px 10px; border-radius: 6px; font-size: 13px; font-weight: bold;">
                                    {label}
                                </span>
                            </td>
                        </tr>
                    </table>
                    <table width="100%" cellpadding="6" cellspacing="0" style="font-size: 12px; border-collapse: collapse; text-align: center; border: 1px solid #eee;">
                        <tr style="background-color: #f9f9f9; color: #555; height: 28px;">
                            <th style="border-bottom: 1px solid #eee;">현재가</th>
                            <th style="border-bottom: 1px solid #eee;">수익률</th>
                            <th style="border-bottom: 1px solid #eee;">진입가</th>
                            <th style="border-bottom: 1px solid #eee;">손절가</th>
                            <th style="border-bottom: 1px solid #eee;">익절가</th>
                            <th style="border-bottom: 1px solid #eee;">보유봉</th>
                        </tr>
                        <tr style="height: 28px;">
                            <td style="font-weight:bold;">{format(int(curr_c), ',') if curr_c != '-' else '-'}</td>
                            <td style="font-weight:bold; color:{profit_color};">{profit}</td>
                            <td>{format(int(entry), ',') if entry != '-' else '-'}</td>
                            <td style="color:#2679ed;">{format(int(stop_p), ',') if stop_p != '-' else '-'}</td>
                            <td style="color:#e22926;">{format(int(target_p), ',') if target_p != '-' else '-'}</td>
                            <td>{bars}</td>
                        </tr>
                    </table>
                </div>
                """

        html += """
            </div>
        </div>
        """
        return html

    def evaluate_financials(self, key, value_str):
        try:
            val = float(value_str.replace('%', '').replace(',', ''))
            if key == 'eps':
                is_good = val > 0
            elif key == 'per':
                is_good = val <= 10
            elif key == 'pbr':
                is_good = val <= 1.0
            elif key == 'roe':
                is_good = val >= 12
            elif key == 'peg':
                is_good = val <= 1.0
            else:
                is_good = True

            if is_good:
                return '<span style="color:#e22926; font-weight:bold;">좋음</span>'
            else:
                return '<span style="color:#555555;">주의</span>'
        except ValueError:
            return "-"

    def get_indicator_style(self, val):
        """지표의 값(G/D, Y/N)에 따라 색상을 반환합니다."""
        if val in ['G', 'Y']:
            return f'<strong style="color:#e22926; font-size: 14px;">{val}</strong>'
        elif val in ['D', 'N']:
            return f'<strong style="color:#2679ed; font-size: 14px;">{val}</strong>'
        return f'<strong style="color:#333; font-size: 14px;">{val}</strong>'

    def create_mail_html(self, stocks_data: list) -> str:
        html = """
        <div style="background-color: #f4f5f7; padding: 20px 10px; font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;">
            <div style="max-width: 400px; margin: 0 auto;">
                <h2 style="text-align: center; color: #333; margin-bottom: 20px;">📈 오늘의 타겟 종목 분석</h2>
        """

        if not stocks_data:
            html += """
                <div style="background-color: #ffffff; padding: 30px 20px; border-radius: 12px; text-align: center; color: #666;">
                    오늘의 조건 검색에 포착된<br>타겟 종목이 없습니다.
                </div>
            """
        else:
            for stock in stocks_data:
                code = stock.get('stock_code', "000000")
                name = stock.get("stock_name", "Unknown")
                today = stock.get("todayStock", {})
                ind = stock.get("indicator", {})
                fin = stock.get("fin", {})

                rate_str = today.get("rate", "0%")
                if rate_str.startswith("-"):
                    rate_bg = "#2679ed"
                elif rate_str == "0%" or rate_str == "0":
                    rate_bg = "#757575"
                else:
                    rate_bg = "#e22926"

                html += f"""
                <div style="background-color: #ffffff; border-radius: 12px; padding: 16px; margin-bottom: 16px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">

                    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 12px;">
                        <tr>
                            <td style="font-size: 18px; font-weight: bold; color: #111;">{name} [{code}]</td>
                            <td align="right">
                                <span style="background-color: {rate_bg}; color: #ffffff; padding: 4px 8px; border-radius: 6px; font-size: 14px; font-weight: bold;">
                                    {rate_str}
                                </span>
                            </td>
                        </tr>
                    </table>

                    <table width="100%" cellpadding="6" cellspacing="0" style="font-size: 12px; border-collapse: collapse; text-align: center; border: 1px solid #eee; margin-bottom: 6px;">
                        <tr style="background-color: #f9f9f9; color: #555; height: 30px;">
                            <th style="border-bottom: 1px solid #eee;">시가</th>
                            <th style="border-bottom: 1px solid #eee;">고가</th>
                            <th style="border-bottom: 1px solid #eee;">저가</th>
                            <th style="border-bottom: 1px solid #eee;">종가</th>
                        </tr>
                        <tr style="height: 30px;">
                            <td>{format(today.get('open'), ',')}</td>
                            <td style="color:#e22926;">{format(today.get('high'), ',')}</td>
                            <td style="color:#2679ed;">{format(today.get('low'), ',')}</td>
                            <td style="font-weight:bold; color:#333;">{format(today.get('close'), ',')}</td>
                        </tr>
                    </table>
                    <div style="font-size: 15px; color: #000; text-align: right; margin-top: 10px; margin-bottom: 16px;">
                        거래량: <strong>{format(today.get('volume'), ',')}</strong>&nbsp;&nbsp;
                    </div>

                    <div style="margin-bottom: 16px;">
                        <div style="font-size: 12px; font-weight: bold; color: #888; margin-bottom: 8px;">기술적 지표</div>

                        <div style="display: flex; justify-content: space-between; text-align: center; gap: 4px;">
                            <div style="background: #f8f9fa; padding: 8px 2px; border-radius: 6px; border: 1px solid #e9ecef; flex: 1;">
                                <div style="font-size: 10px; color: #666; margin-bottom: 4px; letter-spacing: -0.5px;">MACD</div>
                                <div>{self.get_indicator_style(ind.get('macd_cross', '-'))}</div>
                            </div>

                            <div style="background: #f8f9fa; padding: 8px 2px; border-radius: 6px; border: 1px solid #e9ecef; flex: 1;">
                                <div style="font-size: 10px; color: #666; margin-bottom: 4px; letter-spacing: -0.5px;">OBV</div>
                                <div>{self.get_indicator_style(ind.get('obv_cross', '-'))}</div>
                            </div>

                            <div style="background: #f8f9fa; padding: 8px 2px; border-radius: 6px; border: 1px solid #e9ecef; flex: 1;">
                                <div style="font-size: 10px; color: #666; margin-bottom: 4px; letter-spacing: -0.5px;">거래량 급등</div>
                                <div>{self.get_indicator_style(ind.get('is_vol_surge', '-'))}</div>
                            </div>
                        </div>
                        <div style="display: flex; justify-content: space-between; text-align: center; gap: 4px;">



                            <div style="background: #f8f9fa; padding: 8px 2px; border-radius: 6px; border: 1px solid #e9ecef; flex: 1;">
                                <div style="font-size: 10px; color: #666; margin-bottom: 4px; letter-spacing: -0.5px;">볼린저 상단 아래</div>
                                <div>{self.get_indicator_style(ind.get('is_under_bb_upper', '-'))}</div>
                            </div>

                            <div style="background: #f8f9fa; padding: 8px 2px; border-radius: 6px; border: 1px solid #e9ecef; flex: 1;">
                                <div style="font-size: 10px; color: #666; margin-bottom: 4px; letter-spacing: -0.5px;">20일선 위</div>
                                <div>{self.get_indicator_style(ind.get('is_over_on_mid', '-'))}</div>
                            </div>

                            <div style="background: #f8f9fa; padding: 8px 2px; border-radius: 6px; border: 1px solid #e9ecef; flex: 1;">
                                <div style="font-size: 10px; color: #666; margin-bottom: 4px; letter-spacing: -0.5px;">20일선 돌파</div>
                                <div>{self.get_indicator_style(ind.get('is_bb_mid_breakout', '-'))}</div>
                            </div>

                        </div>
                    </div>

                    <div>
                        <div style="font-size: 12px; font-weight: bold; color: #888; margin-bottom: 6px;">재무 지표 분석</div>
                        <table width="100%" cellpadding="6" cellspacing="0" style="font-size: 12px; border-collapse: collapse; text-align: center; border: 1px solid #eee;">
                            <tr style="background-color: #f9f9f9; color: #555; height: 30px;">
                                <th style="border-bottom: 1px solid #eee;">EPS</th>
                                <th style="border-bottom: 1px solid #eee;">PER</th>
                                <th style="border-bottom: 1px solid #eee;">PBR</th>
                                <th style="border-bottom: 1px solid #eee;">ROE</th>
                                <th style="border-bottom: 1px solid #eee;">PEG</th>
                            </tr>
                            <tr style="height: 30px;">
                                <td>{fin.get('eps')}<br>{self.evaluate_financials('eps', fin.get('eps'))}</td>
                                <td>{fin.get('per')}<br>{self.evaluate_financials('per', fin.get('per'))}</td>
                                <td>{fin.get('pbr')}<br>{self.evaluate_financials('pbr', fin.get('pbr'))}</td>
                                <td>{fin.get('roe')}<br>{self.evaluate_financials('roe', fin.get('roe'))}</td>
                                <td>{fin.get('peg')}<br>{self.evaluate_financials('peg', fin.get('peg'))}</td>
                            </tr>
                            <tr style="height: 30px;">
                                <td style="border-bottom: 1px solid #eee;">주당순이익<br>00.0 이상</td>
                                <td style="border-bottom: 1px solid #eee;">주가수익비율<br>10.0 이하</td>
                                <td style="border-bottom: 1px solid #eee;">주가순자산비율<br>01.0 이하</td>
                                <td style="border-bottom: 1px solid #eee;">자기자본이익률<br>12.0 이상</td>
                                <td style="border-bottom: 1px solid #eee;">주가성장비율<br>01.0 이하</td>
                            </tr>
                        </table>
                    </div>

                </div>
                """

        html += """
            </div>
        </div>
        """
        return html