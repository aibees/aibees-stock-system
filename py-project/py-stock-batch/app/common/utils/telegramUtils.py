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

telegramUtils = TelegramSender()
