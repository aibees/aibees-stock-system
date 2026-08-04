from datetime import datetime
import pytz
from html import escape as _esc

# 오늘 날짜 구하는 법
def get_today(types):
    return datetime.now().astimezone(pytz.timezone("Asia/Seoul")).strftime(types)


def get_numeric_timestamp():
    # 한국 시간 기준
    now = datetime.now(pytz.timezone("Asia/Seoul"))

    # 포맷: yyyyMMddHHmmssZzz
    return now.strftime("%Y%m%d%H%M%S")  # ex: 20250607225030


def _fmt(v):
    return _esc("" if v is None else str(v))


def _is_number_like(v):
    s = "" if v is None else str(v).strip()
    if s == "":
        return False
    # 천 단위 콤마 허용
    s = s.replace(",", "")
    try:
        float(s)
        return True
    except ValueError:
        return False


def changeTranslate(txt):
    if txt == 'currency':
        return '통화(코인)'

    if txt == 'balance':
        return '보유량'
    
    if txt == 'avg_buy_price':
        return '평균 매수가'
    
    if txt == 'avg_buy_price_modified':
        return '평단가 조정여부'
    
    if txt == 'unit_currency':
        return '매수 기준통화'

    return txt