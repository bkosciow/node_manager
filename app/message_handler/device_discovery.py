import logging

from message_listener.abstract.handler_interface import Handler

logger = logging.getLogger(__name__)


class MessageHandler(Handler):

    def handle(self, message) -> None:
        if message is None or message.data is None:
            return
        logger.info("Received message: %s", message.data)
