# chip_id Normalization

- Some devices send `chip_id` as int — normalize with `str(raw).strip()`;
  empty result is treated as missing.
- Empty/missing `chip_id` or `node` (including whitespace-only) → skip the
  message with `logger.warning`; it is never queued and never reaches the DB.
- Non-dict `message.data` (list, string, None) → skip without crashing.
- New handlers must apply the same normalization before any cache keying
  or DB work — the dedup cache keys on the normalized pair.
