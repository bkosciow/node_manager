import logging
import signal
import sys
import threading

from message_listener.server import Server
from iot_message.message import Message
from iot_message.cryptor.aes_sha1 import Cryptor as AESSHA1Cryptor

from app.config import settings
from app.message_handler.device_discovery import MessageHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_server: Server | None = None
_stop = threading.Event()


def _shutdown(signum: int, frame: object) -> None:
    if _server:
        logger.info("Shutting down...")
        _server.work = False
    _stop.set()
    sys.exit(0)


def main() -> None:
    global _server

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

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    _server = Server(port=settings.node_listener_port, ip_address="0.0.0.0")
    _server.add_handler("message_handler", MessageHandler())
    _server.start()
    logger.info("Listening on port %d", settings.node_listener_port)

    _stop.wait()


if __name__ == "__main__":
    main()
