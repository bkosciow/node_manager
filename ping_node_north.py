import logging
from iot_message.message import Message
from iot_message.cryptor.aes_sha1 import Cryptor as AESSHA1Cryptor
from app.services import comm
from app.config import settings

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

_message = {
    'event': "system.ping",
    'targets': [node]
}

comm.send(_message)

