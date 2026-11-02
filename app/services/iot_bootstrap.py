"""Shared IoT UDP bootstrap.

Prescribed by ``.ai/standards/messaging/iot-bootstrap.md`` — the only
blessed UDP script preamble. New sender scripts:

    from app.services.iot_bootstrap import bootstrap

    bootstrap(send_to=(settings.node_listener, int(settings.node_listener_port)))

Listener-only scripts: ``bootstrap()``.
"""

import logging

from iot_message.cryptor.aes_sha1 import Cryptor as AESSHA1Cryptor
from iot_message.message import Message

from app.config import settings
from app.services import comm


def bootstrap(send_to: tuple[str, int] | None = None) -> None:
    """Configure UDP messaging. The step order matters — do not reorder."""
    logging.basicConfig(level=logging.INFO)

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

    if send_to is not None:
        comm.address = send_to
