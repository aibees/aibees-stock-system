"""
upbitService.py — Upbit 잔고 조회 서비스

설계 개요:
    1. user_detail 에서 해당 user_id 의 UPBIT access/secret 을 조회
    2. UserOptionMeta 에 access_key / secret_key 를 실어 인증정보 컨테이너로 사용
    3. CcxtUpbit(access, secret) 엔진으로 실제 거래소 잔고를 조회
    4. 프론트/외부 프로젝트가 쓰기 쉬운 형태로 응답을 정형화

인증정보 원천:
    - user_detail.upbit_access_key
    - user_detail.upbit_secret_key
    → UserOptionMeta.access_key / secret_key 로 매핑
"""

import logging

from app.domains.dao.userDetailDao import UserDetailDao
from app.domains.vo.UserOptionMeta import UserOptionMeta
from app.ext_services.upbit.upbitEngine import CcxtUpbit

logging.basicConfig(level=logging.ERROR)


class UpbitService:
    def __init__(self):
        self.name = 'UpbitService'
        self.userDetailDao = UserDetailDao()

    # ── 인증정보 로드 ────────────────────────────────────────────────
    def _load_user_info(self, session, user_id: int) -> UserOptionMeta:
        """
        user_detail 의 UPBIT 인증정보를 UserOptionMeta 에 실어 반환.
        키가 없거나 비어 있으면 ValueError.
        """
        creds = self.userDetailDao.select_upbit_credentials(session, user_id)
        if creds is None:
            raise ValueError(f"user_detail(user_id={user_id}) 레코드를 찾을 수 없습니다.")

        access = creds.get('access')
        secret = creds.get('secret')
        if not access or not secret:
            raise ValueError(f"user_detail(user_id={user_id})에 UPBIT 인증키가 설정되지 않았습니다.")

        user_info = UserOptionMeta()
        user_info.user_id = str(user_id)
        user_info.access_key = access
        user_info.secret_key = secret
        return user_info

    # ── 잔고 조회 ────────────────────────────────────────────────────
    def get_balance(self, session, user_id: int, coin: str | None = None) -> dict:
        """
        user_id 의 UPBIT 잔고를 조회한다.

        coin 지정 시: 해당 코인 단일 잔고 { free, used, total }
        coin 미지정 시: 계좌 요약(KRW 예수금 + 보유 코인 목록)

        반환 예시(coin 미지정):
            {
                "krw_balance": 152340.0,
                "holdings": [
                    {"coin": "BTC", "free": 0.01, "used": 0.0, "total": 0.01},
                    ...
                ]
            }
        """
        user_info = self._load_user_info(session, user_id)
        engine = CcxtUpbit(user_info.access_key, user_info.secret_key)

        # ── 단일 코인 조회 ──────────────────────────────────────────
        if coin:
            coin = coin.upper()
            bal = engine.get_current_balance(coin)
            return {
                'coin': coin,
                'free':  self._to_float(bal.get('free')),
                'used':  self._to_float(bal.get('used')),
                'total': self._to_float(bal.get('total')),
            }

        # ── 계좌 전체 조회 ──────────────────────────────────────────
        balance = engine.get_current_balance()  # ccxt fetch_balance 전체 구조

        # KRW 예수금
        krw = balance.get('KRW') or {}
        krw_balance = self._to_float(krw.get('free'))

        # 보유 코인 목록 (total > 0 인 자산만, KRW 제외)
        totals = balance.get('total') or {}
        free_map = balance.get('free') or {}
        used_map = balance.get('used') or {}

        holdings = []
        for asset, total in totals.items():
            if asset == 'KRW':
                continue
            total_f = self._to_float(total)
            if total_f <= 0:
                continue
            holdings.append({
                'coin':  asset,
                'free':  self._to_float(free_map.get(asset)),
                'used':  self._to_float(used_map.get(asset)),
                'total': total_f,
            })

        return {
            'krw_balance': krw_balance,
            'holdings':    holdings,
        }

    # ── 헬퍼 ─────────────────────────────────────────────────────────
    @staticmethod
    def _to_float(v) -> float:
        try:
            return float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0
