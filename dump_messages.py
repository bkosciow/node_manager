import logging
from iot_message.message import Message
from iot_message.cryptor.aes_sha1 import Cryptor as AESSHA1Cryptor
from app.services import comm
from app.config import settings
from message_listener.abstract.handler_interface import Handler as HandlerInterface
from pprint import pprint
from message_listener.server import Server
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

node = "node-north"

comm.address = (settings.node_listener, int(settings.node_listener_port))


if settings.sl_passphrase:
    cryptor = AESSHA1Cryptor(
        staticiv=settings.sl_statisiv,
        ivkey=settings.sl_ivkey,
        datakey=settings.sl_datakey,
        passphrase=settings.sl_passphrase,
    )
    Message.add_decoder(cryptor)
    Message.add_encoder(cryptor)

Message.node_name = settings.node_name
Message.chip_id = settings.node_id

class DebugHandler(HandlerInterface):
    def handle(self, message):
        # pprint(message.data)
        if message is not None and 'event' in message.data:
            if message['event'] == 'system.pong':
                pprint(message.data)

svr = Server(port=int(settings.node_listener_port))
svr.ignore_missing_decoders = False
svr.add_handler('debug', DebugHandler())

svr.start()

while True:
    time.sleep(1)
