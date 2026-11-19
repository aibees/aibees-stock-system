import logging

from app.flask_app.routers import register_blueprints
from web_shared.app_factory import create_app

logging.basicConfig(level=logging.ERROR)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


class FlaskApp:
    """앱 생성(CORS·요청별 DB 세션)은 web_shared.app_factory 가 한다. 여기서는 이 서버의 블루프린트만 넘긴다."""

    def __init__(self, config_obj):
        self.config = config_obj
        self.app = create_app(register_blueprints, config_obj, import_name='app.flask_app.runner')

    def get_app(self):
        return self.app
