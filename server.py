from message_listener.server import Server
from node_manager.service.config import Config
import node_manager.service.comm as comm
from node_manager.handler.message_handler import MessageHandler
from flask import Flask
from node_manager.api.routes import init_api
import time
import logging
from node_manager.service.microplate import Microplate


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s %(message)s'
)
logging.getLogger('schedule').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def serve(config_file):
    config = Config(config_file)

    # NextCloud talk integration
    if config.section_enabled('nextcloud'):
        from node_manager.service.nextcloud import ErrorHandler
        logging.getLogger().addHandler(ErrorHandler(config))

    # set broadcast socket
    comm.address = (config.get("general.ip"), int(config.get("general.port")))

    microplate = Microplate(config['microplate'])

    # starts a listener thread
    # serverSensor = Server()
    # serverSensor.add_handler('message_handler', MessageHandler())
    # serverSensor.start()

    logger.info("Starting API server")
    app = Flask(__name__)
    init_api(app, config['api'], microplate)

    try:
        app.run(debug=True, host="0.0.0.0", port=int(config.get('api.port')), use_reloader=True)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    logger.info("Starting app")
    serve('config.ini')
