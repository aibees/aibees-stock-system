import os

from flask import Flask, request, g
from flask_cors import CORS
from app.flask_app.router import register_blueprints
from app.config.database import dbConn
import logging

from app.scheduler_app.runner import scheduleManage

logging.basicConfig(level=logging.ERROR)

class FlaskApp:
    def __init__(self, config_obj):
        self.config = config_obj
        self.app = Flask(__name__)
        CORS(
            self.app
           ,allow_headers=['Content-Type', 'maria-Authorization']
           ,methods=['GET', 'POST', 'OPTIONS']     
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
                    db.rollback()  # 에러 발생 시 rollback
                db.close()
            
        self._register_blueprints()
        

    def _register_blueprints(self):
        register_blueprints(self.app)
        
    def get_app(self) -> Flask:
        # scheduler
        #   worker 컨테이너는 SCHEDULER_ENABLED=false 로 자동 스케줄을 끈다.
        #   (메인이 /jobs/once 로 트리거하므로 중복 자동실행 방지)
        #   job 목록 load 는 StockScheduler.__init__ 에서 이미 끝나 있어
        #   start() 를 건너뛰어도 /jobs/once 는 정상 동작한다.
        if os.getenv("SCHEDULER_ENABLED", "true").strip().lower() in ("1", "true", "yes", "y", "on"):
            scheduleManage.start()

        return self.app
    
