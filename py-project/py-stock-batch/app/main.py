import sys
import time

from app.flask_app.runner import FlaskApp
flaskApp = FlaskApp(None).get_app()

def process(args):
    flaskApp.run(host="0.0.0.0", port=5557, threaded=True)

if __name__ == "__main__":
    process(sys.argv)