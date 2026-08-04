import time
from datetime import date, timedelta

from app.batches.jobs.job import Job
from app.batches.services.stockService import StockService
from app.batches.services.userService import UserService
from app.common.utils.smtpUtils import emailUtils
from app.common.utils.telegramUtils import telegramUtils
from stock_shared.vo.userCoinInfo import UserCoinInfo
from stock_shared.dto.userOptionMeta import UserOptionMeta
from app.ext_services.kis.KisEngine import KisEngine
from app.ext_services.kis.component.KisStockService import KisService
from stock_shared.strategy.kospi1 import KospiStrategy1


class StockSellCheckJob(Job):
    """
    보유 종목 매도 타겟 체크 배치.

    동작 흐름 (1회 실행 = 1회 체크):
      1. 매도 알림 설정된 유저 전체 조회 (stock_sell_mail_flag='Y' OR stock_sell_tele_flag='Y')
      2. 유저별로:
         a. 해당 user_id의 enabled_flag='Y' 종목 조회
         b. 각 종목 OHLCV + 지표 계산 → KospiStrategy1.get_action_in_active()
         c. 결과를 trade_sell_target_stock(user_id, stock_code 복합 PK)에 upsert
         d. SELL 시그널 종목은 유저 설정에 따라 email/telegram으로 알림 발송

    ※ 반복 실행은 batch_job_master 의 cron 설정(runner.py)이 담당한다.

    kwargs:
      - lookback_days (int, default=250): OHLCV 조회 일수
    """

    def __init__(self):
        super().__init__()
        self.job_name = 'StockSellCheckJob'
        self.stockServiceImpl = StockService()
        self.userServiceImpl  = UserService()
        self.kis              = KisEngine()
        self.kisServiceImpl   = KisService()
        self.strategy         = KospiStrategy1()

    def get_name(self):
        return self.job_name

    # ──────────────────────────────────────────────────────────────────
    # 배치 진입점
    # ──────────────────────────────────────────────────────────────────
    def run_batch(self, **kwargs):
        lookback_days = int(kwargs.get('lookback_days', 250))

        today      = date.today()
        today_ymd  = today.strftime('%Y%m%d')
        end_date   = today.strftime('%Y-%m-%d')
        start_date = (today - timedelta(days=lookback_days)).strftime('%Y-%m-%d')

        # ── 매도 알림 대상 유저 전체 조회 ──────────────────────────────
        target_users: list[UserOptionMeta] = self.userServiceImpl.get_all_sell_target_users(self.session)

        if not target_users:
            return {
                'status':    'success',
                'batch_cnt': 0,
                'desc':      '매도 알림 설정 유저가 없습니다. (user_options 테이블을 확인하세요)',
            }

        total_checked = 0

        for user in target_users:
            user_id   = user.user_id
            user_name = user.user_name
            print(f'\n[StockSellCheckJob] ▶ 유저: {user_name}(id={user_id})', flush=True)

            # ── 해당 유저의 매도 체크 희망 종목 조회 ──────────────────
            request_list = self.stockServiceImpl.get_sell_request_list(self.session, user_id)

            if not request_list:
                print(f'  → 대상 종목 없음, skip', flush=True)
                continue

            print(f'  → 대상 종목: {len(request_list)}개', flush=True)

            sell_alerts = []

            for request in request_list:
                stock_code  = request['stock_code']
                stock_name  = request.get('stock_name', '')
                entry_price = float(request.get('entry_price') or 0)
                hold_qty    = float(request.get('hold_qty') or 0)
                entry_date  = request.get('entry_date', '')

                print(f'  {stock_name}({stock_code}) 체크 중...', flush=True)

                try:
                    time.sleep(1.5)  # KIS API 호출 제한 대응

                    # ── 1. OHLCV + 지표 계산 ──────────────────────────
                    ohlcv = self.kis.getOHLCV(stock_code, start_date, end_date)
                    if ohlcv is None or len(ohlcv) < 2:
                        print(f'    → 데이터 부족 또는 조회 불가, skip', flush=True)
                        continue

                    computed = self.kisServiceImpl.compute_indicator_df(ohlcv, user_info=user)
                    computed.fillna(0.0, inplace=True)
                    trade_data = computed.to_dict(orient='records')

                    curr_row = trade_data[-1]
                    prev_row = trade_data[-2]

                    # ── 2. 기존 포지션 추적값 로드 (없으면 초기값) ────────
                    existing = self.stockServiceImpl.get_sell_target_by_code(
                        self.session, user_id, stock_code
                    )
                    peak_close      = float((existing or {}).get('peak_close') or entry_price)
                    peak_high       = float((existing or {}).get('peak_high')  or entry_price)
                    bars_since_peak = int((existing or {}).get('bars_since_peak') or 0)
                    entry_atr       = float((existing or {}).get('entry_atr') or 0)

                    # ── 3. 포지션 상태를 UserOptionMeta 에 주입 ────────
                    user.entry_price     = entry_price
                    user.entry_atr       = entry_atr
                    user.bars_held       = self._calc_bars_held(existing, today_ymd)
                    user.peak_close      = peak_close
                    user.peak_high       = peak_high
                    user.bars_since_peak = bars_since_peak
                    user.avg_price       = entry_price

                    # ── 4. UserCoinInfo 생성 ───────────────────────────
                    coin_info = UserCoinInfo.from_dict({**curr_row, 'coin': stock_code})
                    prev_info = UserCoinInfo.from_dict({**prev_row, 'coin': stock_code})

                    # ── 5. 매도 판단 ───────────────────────────────────
                    result      = self.strategy.get_action_in_active(prev_info, coin_info, user)
                    action_type = result.get('action_type', 'HOLD')
                    sell_ctx    = result.get('sell_ctx', {})

                    # ── 6. 포지션 추적값 갱신 ─────────────────────────
                    curr_close = float(curr_row.get('close', 0))
                    curr_high  = float(curr_row.get('high', 0))

                    new_peak_close = max(peak_close, curr_close)
                    new_peak_high  = max(peak_high, curr_high)
                    new_bars_since_peak = (
                        0 if (new_peak_close > peak_close or new_peak_high > peak_high)
                        else bars_since_peak
                    )

                    # ── 7. 결과 upsert ─────────────────────────────────
                    upsert_data = {
                        'user_id':     user_id,
                        # 입력 테이블에서 복사 (스냅샷)
                        'stock_code':  stock_code,
                        'stock_name':  stock_name,
                        'entry_date':  entry_date,
                        'entry_price': entry_price,
                        'entry_atr':   entry_atr,
                        'hold_qty':    hold_qty,
                        # 포지션 추적
                        'bars_held':       user.bars_held,
                        'peak_close':      new_peak_close,
                        'peak_high':       new_peak_high,
                        'bars_since_peak': new_bars_since_peak,
                        'last_check_ymd':  today_ymd,
                        # 현재 시세
                        'curr_open':   curr_row.get('open'),
                        'curr_high':   curr_row.get('high'),
                        'curr_low':    curr_row.get('low'),
                        'curr_close':  curr_close,
                        'curr_volume': curr_row.get('volume'),
                        'curr_rate':   self._calc_rate_str(prev_row, curr_row),
                        # 매도 판단
                        'action_type':  action_type,
                        'profit_pct':   sell_ctx.get('profit_pct'),
                        'stop_price':   sell_ctx.get('stop_price'),
                        'target_price': sell_ctx.get('target_price'),
                        'trail_line':   sell_ctx.get('trail_line'),
                        'sell_reason':  self._build_sell_reason(action_type, sell_ctx),
                    }

                    self.stockServiceImpl.upsert_sell_check_result(self.session, upsert_data)
                    self.session.commit()

                    print(f'    → action={action_type} | profit={sell_ctx.get("profit_pct")} | '
                          f'bars_held={user.bars_held}', flush=True)

                    # ── 8. SELL 시그널 수집 ────────────────────────────
                    if action_type != 'HOLD':
                        sell_alerts.append({
                            **result,
                            'stock_name': stock_name,
                            'stock_code': stock_code,
                        })

                except ConnectionError:
                    print(f'    → 네트워크 오류, 5초 후 재시도...', flush=True)
                    self.session.rollback()
                    time.sleep(5)
                    continue
                except Exception as e:
                    print(f'    → 오류: {str(e)}', flush=True)
                    self.session.rollback()
                    if 'API 호출 횟수를 초과' in str(e):
                        print('    → API 한도 초과, 30초 대기', flush=True)
                        time.sleep(30)
                    continue

            total_checked += len(request_list)

            # ── 유저별 알림 발송 ────────────────────────────────────────
            if sell_alerts:
                self._send_alerts(user, sell_alerts)
            else:
                print(f'  → [{user_name}] 매도 시그널 없음 (전 종목 HOLD)', flush=True)

        desc = f'전체 체크 종목: {total_checked}개 (유저 {len(target_users)}명)'
        print(f'\n[StockSellCheckJob] 완료 — {desc}', flush=True)

        return {
            'status':    'success',
            'batch_cnt': total_checked,
            'desc':      desc,
        }

    # ──────────────────────────────────────────────────────────────────
    # 알림 발송
    # ──────────────────────────────────────────────────────────────────
    def _send_alerts(self, user: UserOptionMeta, sell_list: list) -> None:
        """유저 설정에 따라 email / telegram 알림 발송"""
        subject   = f'[자동알림] 매도 시그널 감지 ({len(sell_list)}건)'

        # ── 이메일 ──────────────────────────────────────────────────
        if user.stock_sell_mail_flag == 'Y' and user.email:
            html_body = self.stockServiceImpl.create_sell_mail_html(sell_list)
            resp = emailUtils.sendMail(subject=subject, body=html_body, receipt=user.email)
            if resp.get('result') == 'success':
                print(f'  ✅ 이메일 발송 → {user.email}', flush=True)
            else:
                print(f'  ❌ 이메일 실패 → {user.email}: {resp.get("msg")}', flush=True)

        # ── 텔레그램 ─────────────────────────────────────────────────
        if user.stock_sell_tele_flag == 'Y' and user.tele_bot_id and user.tele_chat_id:
            resp = telegramUtils.sendSellAlert(
                bot_id=user.tele_bot_id,
                chat_id=user.tele_chat_id,
                sell_list=sell_list
            )
            if resp.get('result') == 'success':
                print(f'  ✅ 텔레그램 발송', flush=True)
            else:
                print(f'  ❌ 텔레그램 실패 → chat_id={user.tele_chat_id}: {resp.get("msg")}', flush=True)

    # ──────────────────────────────────────────────────────────────────
    # helpers
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def _calc_bars_held(existing: dict | None, today_ymd: str) -> int:
        """
        bars_held 계산. last_check_ymd가 오늘이면 그대로, 아니면 +1.
        (같은 날 배치가 여러번 실행돼도 하루에 한 번만 증가)
        """
        if not existing:
            return 1
        current  = int(existing.get('bars_held') or 0)
        last_ymd = existing.get('last_check_ymd') or ''
        return current if last_ymd == today_ymd else current + 1

    @staticmethod
    def _calc_rate_str(prev_row: dict, curr_row: dict) -> str:
        try:
            prev_close = float(prev_row.get('close', 0))
            curr_close = float(curr_row.get('close', 0))
            if prev_close <= 0:
                return '0%'
            return f'{round((curr_close - prev_close) / prev_close * 100, 2)}%'
        except Exception:
            return '0%'

    @staticmethod
    def _build_sell_reason(action_type: str, sell_ctx: dict) -> str:
        reasons = {
            'SELL_STOP_LOSS': f"손절: OBV데드={sell_ctx.get('obv_dead_valid')} / 20일선위={sell_ctx.get('is_above_ema20')}",
            'SELL_PROFIT':    f"익절: 수익률 {sell_ctx.get('profit_pct')} 도달",
            'SELL_TRAIL':     f"트레일링: 고점={sell_ctx.get('peak')} / 라인={sell_ctx.get('trail_line')}",
            'SELL_TIME':      f"타임스탑: 보유={sell_ctx.get('bars_held')}봉 / hard_cap={sell_ctx.get('over_hard')}",
            'HOLD':           '',
        }
        return reasons.get(action_type, action_type)
