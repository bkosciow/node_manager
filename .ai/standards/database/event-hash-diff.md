# Event & Hash-Diff Semantics

Device-side file hashes live in `DeviceEvent.parameters` (JSON) under protocol-defined event types — no dedicated table:

- Event type format: `system.{repo_type}.hash` (e.g., `system.microplate.hash`). Protocol-defined — **devices send these strings, so never rename**.
- `parameters` is a `{filename: sha256}` dict; one row per `(device_id, event_type)` (`uq_device_event_type`).

Diff semantics (`check_update_available`, `get_repo_file_diff` in `app/crud/update_status.py`):

- Device hashes come from the device's `system.{repo_type}.hash` event. Never reported (`None`) → no diff (`False` / `[]`).
- A file present on only one side → diff. Comparison excludes ignored files (`DeviceIgnoredFile` rows for the device + repo_type).
- `get_repo_file_diff` returns sorted `{"filename", "device_hash", "repo_hash"}` entries; a side's `None` means "exists only on the other side".

**Trap:** `get_device_updates` hardcodes the repo types `("microplate", "userspace")` — adding a new repo type requires updating that tuple and its result-dict keys.
