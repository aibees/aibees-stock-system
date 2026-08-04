from datetime import datetime
import pytz

# 오늘 날짜 구하는 법
def get_today(types):
    return datetime.now().astimezone(pytz.timezone("Asia/Seoul")).strftime(types)

def get_numeric_timestamp():
    # 한국 시간 기준
    now = datetime.now(pytz.timezone("Asia/Seoul"))

    # 포맷: yyyyMMddHHmmssZzz
    return now.strftime("%Y%m%d%H%M%S")  # ex: 20250607225030