from flask import Flask, request, g
from flask_cors import CORS
from app.flask_app.routers import register_blueprints
from app.config.db.database import dbConn
import logging
from app.flask_app.utils.apiResponse import ApiResponse
logging.basicConfig(level=logging.ERROR)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

class FlaskApp:
    def __init__(self, config_obj):
        self.config = config_obj
        self.app = Flask(__name__)
        CORS(
            self.app,
            resources={r"/api/*": {
                "origins": "*",
                # Authorization 헤더 누락 시 preflight 단계에서 차단되므로 명시
                "allow_headers": ["Content-Type", "Authorization", "maria-Authorization"],
                "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                # "supports_credentials": True,
            }}
        )
        if config_obj:
            self.app.config.from_object(config_obj)
            
        # 요청 시작 시 DB 세션 생성
        @self.app.before_request
        def before_request():
            g.db = dbConn.get_session()

        # 요청 종료 시 세션 정리
        @self.app.teardown_appcontext
        def teardown_db(exception):
            db = g.pop('db', None)
            if db is not None:
                if exception:
                    logging.exception(exception)
                    db.rollback()
                else:
                    db.commit()
                # scoped_session은 close()가 아닌 remove()로 정리해야
                # 스레드-로컬 레지스트리에서 완전히 제거됨.
                # close()만 호출하면 다음 요청이 같은 스레드에서 처리될 때
                # 닫힌 세션을 재사용하는 문제가 생길 수 있음.
                db.remove()
            
        #self._register_before_request()
        self._register_blueprints()
        
        # @self.app.errorhandler(Exception)
        # def handle_exception(e):
        #     print(e)
        #     print("errorHandler context")
        #     logging.exception(e)
        #     # 트랜잭션 정리
        #     db = g.pop('db', None)
        #     if db:
        #         db.rollback()
        #         db.close()

        #     return ApiResponse.error(str(e)), 500

    def _register_blueprints(self):
        register_blueprints(self.app)
        
    # def _register_before_request(self):
        
    #     @self.app.before_request
    #     def before_any_request():
    #         print(f"[BeforeRequest] 요청 경로: {request.path}")
    #         print(f'maria-autho ==> {request.headers.get("maria-Authorization")}')
    #         # 예: 인증 필터
    #         if request.path.startswith("/api/v") and (not request.headers.get("maria-Authorization") or request.headers.get('maria-Autorization') != 'maria-batch-app'):
    #             return {"error": "Unauthorized"}, 401

    def get_app(self) -> Flask:
        return self.app
    
