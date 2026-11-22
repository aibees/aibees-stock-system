import logging

from app.flask_app.routers import register_blueprints
from web_shared.app_factory import create_app
from web_shared.auth.features import register_feature_provider
from web_shared.auth.service import configure_consent_versions
from app.services.honey_service import extra_features as honey_extra_features

# 양봉상회 약관·개인정보 처리방침 버전. 앱(yangbong-store-vue src/scripts/termsOfService.js, privacyPolicy.js)과 같아야 한다.
# 바꾸면 기존 회원은 다음 로그인 때 새 문서에 다시 동의한다. 비밀상회 버전은 web_shared 기본값 그대로다.
YANGBONG_TERMS_VERSION = '2026-12-01'
YANGBONG_PRIVACY_VERSION = '2026-12-01'

logging.basicConfig(level=logging.ERROR)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


class FlaskApp:
    """앱 생성(CORS·요청별 DB 세션)은 web_shared.app_factory 가 한다. 여기서는 양봉상회 블루프린트만 넘긴다."""

    def __init__(self, config_obj):
        self.config = config_obj
        configure_consent_versions(YANGBONG_TERMS_VERSION, YANGBONG_PRIVACY_VERSION)
        # 꿀로 산 프리미엄 하루 이용권을 쓰는 동안 RECO_ADVANCED 를 더한다(비밀상회는 등록하지 않는다)
        register_feature_provider(honey_extra_features)
        self.app = create_app(register_blueprints, config_obj, import_name='app.flask_app.runner')

    def get_app(self):
        return self.app
