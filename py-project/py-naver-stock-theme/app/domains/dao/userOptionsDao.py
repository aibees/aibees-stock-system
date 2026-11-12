from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.dialects.mysql import insert

from stock_shared.dao.baseDao import BaseDao
from stock_shared.dao.userOptionRecoDao import UserOptionRecoDao
from stock_shared.models.userOptionReco import UserOptionReco
from stock_shared.models.userOptions import UserOptions
from stock_shared.models.userMaster import UserMaster
from stock_shared.models.userDetail import UserDetail

import logging
logging.basicConfig(level=logging.ERROR)

#: user_option_reco 중 API 로 주고받지 않는 컬럼 (미참조, 롤백 대비 보존)
_RECO_HIDDEN_KEYS = frozenset({'trail_basis'})


class UserOptionsDao(BaseDao):
    model = UserOptions

    def __init__(self):
        self.__name__ = 'UserOptionsDao'

    # select all
    # ================================================================
    # BaseDao.select_all 을 그대로 사용합니다.

    # select by user_id
    # ================================================================
    def select_by_user_id(self, session, user_id: int):
        stmt = select(UserOptions).where(UserOptions.user_id == user_id)
        result = session.execute(stmt).scalars().first()
        return result.to_dict() if result else None

    # ----------------------------------------------------------------
    # 개인설정 조회 — 3개 테이블 통합 (GET /api/v1/user-options)
    # ----------------------------------------------------------------
    def select_user_settings(self, session, user_id: int, is_admin: bool) -> dict:
        """user_master / user_detail / user_options 3개 테이블에서 설정 조회."""

        # user_master
        um = session.execute(
            select(UserMaster).where(UserMaster.user_id == user_id)
        ).scalars().first()

        # user_detail
        ud = session.execute(
            select(UserDetail).where(UserDetail.user_id == user_id)
        ).scalars().first()

        # user_options
        uo = session.execute(
            select(UserOptions).where(UserOptions.user_id == user_id)
        ).scalars().first()

        def _f(v):
            return float(v) if v is not None else None

        result = {
            'user_master': {
                'user_phone': um.user_phone if um else None,
                'email': um.email if um else None,
            },
            'user_detail': {
                'kis_id': ud.kis_id if ud else None,
                'kis_account': ud.kis_account if ud else None,
                'kis_access_key': ud.kis_access_key if ud else None,
                'kis_secret_key': ud.kis_secret_key if ud else None,
                'tele_bot_id': ud.tele_bot_id if ud else None,
                'tele_chat_id': ud.tele_chat_id if ud else None,
            },
            'user_options': {
                'stock_sell_mail_flag':       uo.stock_sell_mail_flag if uo else None,
                'stock_buy_target_mail_flag': uo.stock_buy_target_mail_flag if uo else None,
                'stock_sell_tele_flag':       uo.stock_sell_tele_flag if uo else None,
            },
        }

        if is_admin:
            result['user_options']['vol_limit'] = uo.vol_limit if uo else None
            result['user_options']['vol_surge'] = _f(uo.vol_surge) if uo else None

        return result

    # ----------------------------------------------------------------
    # user_master 부분 UPDATE
    # ----------------------------------------------------------------
    def update_user_master(self, session, user_id: int, fields: dict) -> None:
        """화이트리스트 컬럼만 UPDATE."""
        ALLOWED = {'user_phone', 'email'}
        values = {k: v for k, v in fields.items() if k in ALLOWED}
        if not values:
            return
        session.execute(
            update(UserMaster).where(UserMaster.user_id == user_id).values(**values)
        )

    # ----------------------------------------------------------------
    # user_detail UPSERT (kis/tele 4개 컬럼)
    # ----------------------------------------------------------------
    def update_user_detail(self, session, user_id: int, fields: dict) -> None:
        """화이트리스트 컬럼만 UPDATE (user_detail은 회원가입 시 이미 존재)."""
        ALLOWED = {'kis_id', 'kis_account', 'kis_access_key', 'kis_secret_key', 'tele_bot_id', 'tele_chat_id'}
        values = {k: v for k, v in fields.items() if k in ALLOWED}
        if not values:
            return
        session.execute(
            update(UserDetail).where(UserDetail.user_id == user_id).values(**values)
        )

    # ----------------------------------------------------------------
    # user_options UPSERT (화이트리스트 컬럼만)
    # ----------------------------------------------------------------
    def upsert_user_options(self, session, user_id: int, fields: dict, is_admin: bool) -> None:
        """화이트리스트 컬럼만 UPSERT. 관리자 전용 컬럼은 is_admin 일 때만 허용."""
        ALLOWED_ALL = {
            'stock_sell_mail_flag', 'stock_buy_target_mail_flag', 'stock_sell_tele_flag',
        }
        ALLOWED_ADMIN = {'vol_limit', 'vol_surge'}

        values = {k: v for k, v in fields.items() if k in ALLOWED_ALL}
        if is_admin:
            values.update({k: v for k, v in fields.items() if k in ALLOWED_ADMIN})

        if not values:
            return
        stmt = insert(UserOptions).values(user_id=user_id, **values)
        session.execute(stmt.on_duplicate_key_update(**values))

    # upsert (기존 메서드 — 다른 곳에서 사용 중이므로 유지)
    # ================================================================
    def upsert(self, session, data: dict) -> None:
        cols = [
            'upbit_push_flag', 'stock_sell_mail_flag', 'stock_buy_target_mail_flag',
            'stock_sell_tele_flag', 'buy_confirm', 'buy_entry', 'sell_entry', 'sell_exit',
            'user_balance', 'ratio_trend', 'ratio_momentum', 'ratio_volatility', 'ratio_volume',
            'time_frame', 'macd_recent_day', 'bb_over_recent_day', 'vol_limit', 'vol_surge',
        ]
        values = {c: data.get(c) for c in cols}
        stmt = insert(UserOptions).values(user_id=data['user_id'], **values)
        session.execute(stmt.on_duplicate_key_update(**values))

    # ----------------------------------------------------------------
    # 추천매수(RECO) 전략 파라미터 조회 (GET /api/v1/strategy/options)
    # ----------------------------------------------------------------
    def select_reco_options(self, session, user_id: int) -> dict | None:
        """user_option_reco 의 파라미터를 접두어 없는 키로 반환. 행 없으면 None.

        DECIMAL 은 float 로 바꿔 내려준다(JSON 직렬화·화면 계산용).
        trail_basis 는 롤백 대비로만 남긴 미참조 컬럼이라 API 에 노출하지 않는다.
        """
        row = UserOptionRecoDao().select_by_user(session, user_id)
        if not row:
            return None
        return {
            k: (float(v) if isinstance(v, Decimal) else v)
            for k, v in row.items()
            if k in UserOptionReco.PARAM_KEYS and k not in _RECO_HIDDEN_KEYS
        }

    # ----------------------------------------------------------------
    # 추천매수(RECO) 전략 파라미터 UPSERT (PATCH /api/v1/strategy/options)
    # ----------------------------------------------------------------
    def upsert_reco_options(self, session, user_id: int, fields: dict) -> None:
        """user_option_reco 에 저장. 키 검증(화이트리스트·관리자 전용)은 라우터에서 끝낸다.

        여기서는 테이블에 있는 컬럼(PARAM_KEYS)만 통과시킨다.
        """
        values = {k: v for k, v in fields.items()
                  if k in UserOptionReco.PARAM_KEYS and k not in _RECO_HIDDEN_KEYS}
        if not values:
            return
        UserOptionRecoDao().upsert(session, user_id, values)

    # update_by_key / delete_by_key : BaseDao 공통 메서드 사용
