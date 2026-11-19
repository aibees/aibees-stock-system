"""
비밀상회 API 서버 설정.

2026-11-19 웹서버 분리(3단계): 양봉상회 API 는 py-yangbong-api 로 나갔다. 이 서버는 비밀상회 전용이다.
  APP_SERVICE=yangbong 으로 이 이미지를 띄우면 양봉 기능(작업 큐·알림·홈 TOP 3 등)이 없는 채로 떠 버리므로 막는다.

환경변수:
    KIS_ENABLED : KIS(한국투자증권) 조회를 쓸지. 기본 true.
                  꺼져 있으면 차트·추천 기록은 DB 일봉(stock_ohlcv_daily, 전 거래일까지)으로 그리고,
                  재무처럼 KIS 로만 받는 정보는 '아직 제공하지 않음'으로 응답한다.
"""
import os

from dotenv import load_dotenv

load_dotenv()   # 로컬 실행용(.env). 운영은 docker-compose env_file 이 이미 넣어 준다.


def _as_bool(value, default):
    if value is None or str(value).strip() == '':
        return default
    return str(value).strip().lower() in ('1', 'true', 'yes', 'y', 'on')


_APP_SERVICE = (os.environ.get('APP_SERVICE') or 'secret').strip().lower()
if _APP_SERVICE != 'secret':
    raise RuntimeError(
        f"이 서버(py-secret-api)는 비밀상회 전용입니다(APP_SERVICE={_APP_SERVICE!r}). "
        "양봉상회 API 는 py-yangbong-api 이미지로 띄웁니다.")

KIS_ENABLED = _as_bool(os.environ.get('KIS_ENABLED'), default=True)


class KisDisabledError(Exception):
    """이 서버는 KIS 조회를 쓰지 않는다(KIS_ENABLED=false)."""

    def __init__(self, what: str = '이 정보'):
        super().__init__(f"{what}는 아직 제공하지 않습니다.")
