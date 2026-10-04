"""PyKis 클라이언트 생성 — 두 앱이 각자 들고 있던 생성 코드를 한 곳으로.

토큰 캐시 정책(keep_token)을 여기 한 곳에 둔다.
  keep_token=True → ~/.pykis/cache 에 토큰을 캐시한다. 컨테이너 안의 모든 프로세스
  (스케줄러가 띄우는 자식 프로세스 포함)가 같은 캐시를 공유해 토큰은 1회 발급 후
  24시간 재사용된다. KIS 는 토큰 발급을 1분 1회로 제한(EGW00133)하므로 이 값이
  꺼지면 프로세스가 뜰 때마다 발급을 시도하다 막힌다.

pykis 를 라이브러리째 걷어낼 계획이 있어서, 앱 코드가 PyKis 생성자를 직접 부르지 않고
이 함수를 거치게 해 두면 교체 지점이 한 곳이 된다.
"""
from __future__ import annotations

from typing import Optional


def create_pykis(*, id: str, account: str, app_key: str, sec_key: str,
                 virtual_id: Optional[str] = None,
                 virtual_app_key: Optional[str] = None,
                 virtual_sec_key: Optional[str] = None,
                 keep_token: bool = True):
    """PyKis 인스턴스를 만든다.

    virtual_* 는 모의투자 계정이 함께 필요할 때만 준다. 하나라도 있으면 세 값을 모두 넘긴다
    (PyKis 는 모의투자 id/appkey/secretkey 를 한 묶음으로 받는다).
    pykis 는 여기서 지연 import — 이 모듈을 import 하는 것만으로는 python-kis 가 필요 없다.
    """
    from pykis import PyKis

    kwargs = dict(id=id, account=account, appkey=app_key,
                  secretkey=sec_key, keep_token=keep_token)
    if virtual_id is not None or virtual_app_key is not None or virtual_sec_key is not None:
        kwargs.update(virtual_id=virtual_id,
                      virtual_appkey=virtual_app_key,
                      virtual_secretkey=virtual_sec_key)
    return PyKis(**kwargs)
