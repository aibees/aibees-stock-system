"""
이 API 프로세스가 어느 서비스로 떠 있는지 — 같은 코드를 비밀상회·양봉상회 두 서버로 띄운다.

환경변수:
    APP_SERVICE : 'secret'(기본, 비밀상회) | 'yangbong'(양봉상회)
    KIS_ENABLED : KIS(한국투자증권) 조회를 쓸지. 기본은 비밀상회 true / 양봉상회 false.
                  양봉상회 DB 회원 정보에는 KIS 키가 없으므로(yangbong/005 에서 일부러 뺌) 양봉상회는 끈다.
                  꺼져 있으면 차트·추천 기록은 DB 일봉(stock_ohlcv_daily, 전 거래일까지)으로 그리고,
                  재무·뉴스처럼 KIS 로만 받는 정보는 '아직 제공하지 않음'으로 응답한다.
"""
import os

from dotenv import load_dotenv

load_dotenv()   # 로컬 실행용(.env). 운영은 docker-compose env_file 이 이미 넣어 준다.

SECRET = 'secret'
YANGBONG = 'yangbong'


def _as_bool(value, default):
    if value is None or str(value).strip() == '':
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'y', 'on')


APP_SERVICE = (os.environ.get('APP_SERVICE') or SECRET).strip().lower()
if APP_SERVICE not in (SECRET, YANGBONG):
    raise RuntimeError(f"APP_SERVICE 는 '{SECRET}' 또는 '{YANGBONG}' 이어야 합니다: {APP_SERVICE!r}")

IS_YANGBONG = APP_SERVICE == YANGBONG
KIS_ENABLED = _as_bool(os.environ.get('KIS_ENABLED'), default=not IS_YANGBONG)


class KisDisabledError(Exception):
    """이 서버는 KIS 조회를 쓰지 않는다(KIS_ENABLED=false)."""

    def __init__(self, what: str = '이 정보'):
        super().__init__(f"{what}는 아직 제공하지 않습니다.")
