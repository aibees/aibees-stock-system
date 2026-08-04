import urllib.request
import urllib.parse
import json


class TelegramSender:
    """
    user_detail 테이블의 tele_bot_id / tele_chat_id를 사용해
    유저별로 텔레그램 메시지를 발송하는 유틸.

    사용 예:
        telegramUtils.sendMessage(
            bot_id='123456:ABC-xxx',
            chat_id='987654321',
            text='📉 매도 시그널 감지: 삼성전자(005930)'
        )
    """

    BASE_URL = 'https://api.telegram.org/bot{bot_id}/sendMessage'

    def sendMessage(self, bot_id: str, chat_id: str, text: str) -> dict:
        """
        텍스트 메시지 발송.

        :param bot_id:   BotFather에서 발급받은 토큰 (user_detail.tele_bot_id)
        :param chat_id:  수신자 chat_id (user_detail.tele_chat_id)
        :param text:     발송할 메시지 (HTML 모드 지원)
        :return:         {'result': 'success'} 또는 {'result': 'fail', 'msg': ...}
        """
        if not bot_id or not chat_id:
            return {'result': 'fail', 'msg': 'tele_bot_id 또는 tele_chat_id가 비어있습니다.'}

        url = self.BASE_URL.format(bot_id=bot_id)
        payload = json.dumps({
            'chat_id':    chat_id,
            'text':       text,
            'parse_mode': 'HTML',
        }).encode('utf-8')

        req = urllib.request.Request(
            url,
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read().decode('utf-8'))
                if body.get('ok'):
                    return {'result': 'success'}
                return {'result': 'fail', 'msg': body.get('description', 'unknown error')}
        except Exception as e:
            return {'result': 'fail', 'msg': str(e)}

    def sendSellAlert(self, bot_id: str, chat_id: str, sell_list: list) -> dict:
        """
        매도 시그널 종목 리스트를 텔레그램으로 발송.

        :param sell_list: StockSellCheckJob의 sell_alerts 리스트
                          각 항목: {'stock_name', 'stock_code', 'action_type', 'sell_ctx'}
        """
        action_label = {
            'SELL_STOP_LOSS': '🛑 손절',
            'SELL_PROFIT':    '✅ 익절',
            'SELL_TRAIL':     '📊 트레일링 스탑',
            'SELL_TIME':      '⏱ 타임스탑',
        }

        lines = [f'<b>📉 매도 시그널 감지 ({len(sell_list)}건)</b>\n']
        for stock in sell_list:
            name       = stock.get('stock_name', '')
            code       = stock.get('stock_code', '')
            action     = stock.get('action_type', '')
            sell_ctx   = stock.get('sell_ctx', {})
            label      = action_label.get(action, action)
            profit     = sell_ctx.get('profit_pct', '-')
            stop_p     = sell_ctx.get('stop_price', '-')
            target_p   = sell_ctx.get('target_price', '-')
            bars       = sell_ctx.get('bars_held', '-')

            lines.append(
                f'▪ <b>{name} [{code}]</b>  {label}\n'
                f'  수익률: {profit} | 보유봉: {bars}\n'
                f'  손절가: {int(stop_p):,}  익절가: {int(target_p):,}'
                if stop_p not in ('-', None) and target_p not in ('-', None)
                else f'▪ <b>{name} [{code}]</b>  {label}\n'
                     f'  수익률: {profit} | 보유봉: {bars}'
            )

        text = '\n'.join(lines)
        return self.sendMessage(bot_id=bot_id, chat_id=chat_id, text=text)


telegramUtils = TelegramSender()
