"""
KIS 자격증명 로더 — 어댑터.

구현은 stock_shared.kis.credentials 로 옮겼다(py-naver-stock-theme 와 공용).
이 파일에 남은 것은 batch 앱 전용인 **AES 복호화 주입**뿐이다 — aes.key 와 aesUtils 가
이 앱에만 있어서 shared 가 가져갈 수 없다.

기존 import 경로(app.ext_services.kis.keyLoader)를 그대로 지킨다:
    KisEngine / StockBuyCheckJob / TradeCandleBackfillJob 가 이 경로를 쓴다.

worker 컨테이너는 KIS_USER_ID(=1/2/3...) 만 다르게 하여 같은 이미지로 뜬다. 이 로더가 그 값으로
user_detail 에서 자기 유저의 KIS key 를 조회한다. 우선순위와 정본 컬럼은
stock_shared.kis.credentials 의 docstring 참고.
"""
from app.common.utils.aesUtils import aesUtils
from stock_shared.kis.credentials import (  # noqa: F401  (list_kis_user_ids 는 재노출)
    list_kis_user_ids,
    resolve_kis_creds as _resolve_kis_creds,
)


def resolve_kis_creds(user_id=None, key_path: str = "kis.key") -> dict:
    """user_id/env 기준으로 실전 자격증명을 해석해 dict 로 반환 (batch 정책: 파일 폴백 허용)."""
    return _resolve_kis_creds(user_id, key_path, decrypt=aesUtils.decrypt)
