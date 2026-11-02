# IoT UDP Script Bootstrap

Standalone UDP scripts must NOT hand-write the preamble. Target state: a shared
helper `app/services/iot_bootstrap.py` (not yet extracted — see last rule).

New sender scripts:

```python
from app.services.iot_bootstrap import bootstrap

bootstrap(send_to=(settings.node_listener, int(settings.node_listener_port)))
```

Listener-only scripts: `bootstrap()` (skip `send_to`).

What the block does (order matters):

1. `logging.basicConfig(level=logging.INFO)`
2. Crypto — only if `settings.sl_passphrase` is set:
   `AESSHA1Cryptor(staticiv=sl_statisiv, ivkey=sl_ivkey, datakey=sl_datakey,
   passphrase=sl_passphrase)`, registered with BOTH `Message.add_decoder`
   and `Message.add_encoder` (the iot_message library is process-global;
   peer key material must match)
3. Identity: `Message.node_name = settings.node_name`,
   `Message.chip_id = settings.node_id`
4. `comm.address = send_to` — senders only; listener-only scripts may skip

Rules:

- `sl_*` key material comes only from settings — never hardcode keys
- `comm.send()` must not be called before bootstrap
- Existing scripts (device_scaner.py, dump_messages.py, ping_node_north.py)
  still carry the block copy-pasted — when touching them, refactor to the
  helper; don't extend the copy-paste
