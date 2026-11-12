import logging


from stock_shared.dao.userMasterDao import UserMasterDao
from stock_shared.dao.userOptionEtfSwitchDao import UserOptionEtfSwitchDao
from stock_shared.dao.userOptionRecoDao import UserOptionRecoDao
from stock_shared.dto.userOptionMeta import UserOptionMeta


# user_options 의 레거시 지표 컬럼 기본값.
#   이 값들은 화면에서 비워둘 수 있어 NULL 로 들어오는 유저가 있는데(user 2/3/4/6),
#   예전엔 `x['macd_recent_day']` 로 직접 대입해 UserOptionMeta 의 기본값을 None 으로
#   덮어썼다. 그 None 이 KisStockService.compute_indicator_df 의
#   rolling(window=None) 까지 흘러가 "window must be an integer 0 or greater" 로 터지고,
#   일봉 지표 전체 → 초기 라인/일별 평가가 전부 실패했다(2026-09-29 user_id=3).
#   UserOptionMeta 쪽 기본값(0)은 rolling 에 넣으면 전부 NaN 이라 쓸모가 없어서,
#   실제로 동작 중인 유저(1/5)와 같은 값을 여기서 명시한다.
_DEFAULT_MACD_RECENT_DAY = 5
_DEFAULT_BB_OVER_RECENT_DAY = 5
_DEFAULT_VOL_LIMIT = 500000
_DEFAULT_VOL_SURGE = 3.0


def _or_default(v, default):
    """NULL(None) 이면 기본값. 0/빈값은 사용자가 의도한 값일 수 있어 그대로 둔다."""
    return default if v is None else v


def extractor(x) -> UserOptionMeta:
    user_meta = UserOptionMeta()
    user_meta.email        = x['email']
    user_meta.user_name    = x['user_name']
    user_meta.user_id      = x['user_id']
    user_meta.macd_recent_day    = _or_default(x['macd_recent_day'], _DEFAULT_MACD_RECENT_DAY)
    user_meta.bb_over_recent_day = _or_default(x['bb_over_recent_day'], _DEFAULT_BB_OVER_RECENT_DAY)
    user_meta.vol_limit    = _or_default(x['vol_limit'], _DEFAULT_VOL_LIMIT)
    user_meta.vol_surge    = _or_default(x['vol_surge'], _DEFAULT_VOL_SURGE)
    # 메신저 설정
    user_meta.tele_bot_id          = x.get('tele_bot_id', '')
    user_meta.tele_chat_id         = x.get('tele_chat_id', '')
    user_meta.stock_sell_mail_flag = x.get('stock_sell_mail_flag', 'N')
    user_meta.stock_sell_tele_flag = x.get('stock_sell_tele_flag', 'N')
    return user_meta


class UserService:
    def __init__(self):
        self.__name__ = 'UserService'
        self.userMasterDaoImpl = UserMasterDao()

    def get_user_options(self, session, user_id: int = 1) -> UserOptionMeta:
        result = self.userMasterDaoImpl.select_user_stock_options(session, {'user_id': user_id})
        meta = extractor(result)
        self._apply_mode_options(session, user_id, meta)
        return meta

    #: (모드별 옵션 DAO, 조회 실패 시 예외를 올릴지). 메타 접두어는 각 DAO 의 META_PREFIX.
    #:   RECO 는 실매매 중인 모드라 조회 실패를 삼키면 손절·익절이 조용히 기본값으로 바뀐다
    #:   → 예외를 올려 기동/재구성을 실패시킨다. ETF_SWITCH 는 아직 executor 가 없어 기본값으로 둔다.
    _MODE_OPTION_DAOS = ((UserOptionRecoDao, True), (UserOptionEtfSwitchDao, False))

    @classmethod
    def _apply_mode_options(cls, session, user_id: int, meta: UserOptionMeta) -> None:
        """모드별 옵션 테이블(user_option_reco, user_option_etf_switch)을 메타에 얹는다.

        user_options 는 전역 설정이고 모드별 파라미터는 별도 테이블에 있다.
        메타에는 reco_* / etf_switch_* 로 접두어를 붙여 flat 하게 담는다.
        행이 없으면(= 아직 설정 안 함) 아무것도 덮지 않는다 → 전략 클래스 기본값.
        조회 실패 처리는 _MODE_OPTION_DAOS 의 두 번째 값을 따른다.
        """
        for dao_cls, required in cls._MODE_OPTION_DAOS:
            dao = dao_cls()
            try:
                for k, v in dao.select_prefixed(session, user_id).items():
                    setattr(meta, k, v)
            except Exception as e:  # noqa: BLE001
                if required:
                    raise
                logging.warning('%s 조회 실패(user_id=%s) → 기본값 사용: %s',
                                dao.model.__tablename__, user_id, e)

    def get_user_email_by_condition(self, session, option):
        if option == 'email':
            return self.userMasterDaoImpl.select_target_emails(session)
        return []
