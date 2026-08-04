from flask import Flask

from app.flask_app.router.router_job import job_bp

def register_blueprints(app: Flask):
    app.register_blueprint(job_bp, url_prefix="/api/v1/jobs")
