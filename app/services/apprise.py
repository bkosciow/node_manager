import requests
import json
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class Apprise:
    def __init__(self):
        self.headers = {
            'content-type': 'application/json',
        }

    def info(self, message, title=""):
        if not settings.apprise_url:
            return

        response = requests.post(
            settings.apprise_url,
            headers=self.headers,
            data=json.dumps({
                'body': message,
                'title': title,
                "tag": settings.apprise_tag
            })
        )
        if response.status_code > 299:
            logging.error(response.status_code)
            logging.error(response.content)


class ErrorHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self=self)
        self.headers = {
            'content-type': 'application/json',
        }
        self.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s %(message)s'))
        self.setLevel(logging.ERROR)

    def emit(self, record):
        if not settings.apprise_url:
            return
        try:
            requests.post(
                settings.apprise_url,
                headers=self.headers,
                data=json.dumps({
                    'body': self.format(record),
                    'title': "Error",
                    "tag": settings.apprise_tag
                })
            )
        except Exception as e:
            print(e)
