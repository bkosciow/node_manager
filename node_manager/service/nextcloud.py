import logging
import json
import requests


class ErrorHandler(logging.Handler):
    def __init__(self, cfg):
        logging.Handler.__init__(self=self)
        self.talk_url = cfg.get('nextcloud.url')
        self.auth = (cfg.get('nextcloud.user'), cfg.get('nextcloud.token'))
        self.headers = {
            'accept': 'application/json, text/plain, */*',
            'cache-control': 'no-cache',
            'content-type': 'application/json',
            'OCS-APIRequest': 'true'
        }
        self.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s %(message)s'))

    def emit(self, record):
        data = {
            'message': self.format(record)
        }
        try:
            response = requests.post(self.talk_url, auth=self.auth, headers=self.headers, data=json.dumps(data))
        except Exception as e:
            print(e)

