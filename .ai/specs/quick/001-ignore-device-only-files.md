# 001 — Device-only files must not set the upgrade flag

**Status:** done (code fix) — live verification on node-north-001 remains
**Date:** 2026-11-02
**Spec:** follows SPEC-001 (node update process), task 14 manual-verification trail

## Context

Files that exist on the device but not in the assigned repository
(microplate or userspace — node-local scripts, secrets, stray files)
showed up in the union diff and set `updates_available` to `true`.
Such files can never be "updated away" by an upgrade (the upgrade only
pushes repo state, it never removes device files), so they must not
trigger the flag. At most they are information shown in the device
detail's `updatable_files`.

Original approach (this file's first version) was to seed
`DeviceIgnoredFile` rows per device-only file on the dev node. That is
a workaround: every new node with local files would need manual rows.
The structural fix is to make the flag comparison **repo-driven**
instead.

## What to do

1. **`check_update_available`** (`app/crud/update_status.py`) — iterate
   **repo files only**: flag is true iff some repo file is missing on
   the device or its hash differs. Device-only files are never counted.
   Edge: empty repo → no flag (nothing to push).
2. **`get_repo_file_diff`** — unchanged union semantics: device-only
   entries (`repo_hash` = null) stay in the list as informational
   entries (device detail view; the trigger already excludes them via
   `repo_hash is not None`).
3. **Ignore filter on both sides** — `DeviceIgnoredFile` rows are now
   excluded from *both* the device and repo hash dicts. Previously only
   the device side was filtered, so an ignored file present on both
   sides still set the flag — and the trigger would have pushed it.

## Implementation Checklist

- [x] `check_update_available` repo-driven
- [x] ignored files filtered from both sides of the diff
- [x] unit tests updated (`test_update_status.py`, `test_ignored_files.py`)
- [x] `pytest tests/ -q` (223 passed) + flake8 clean
- [x] SPEC-001 changelog + "Device-only diff entries" consequences updated
- [ ] Live check on dev: `GET /api/devices` on node 1 — microplate
      flag cleared, userspace flag true only because of `main.py`
      (the genuine pending update)
- [ ] Optional close of the loop: `POST /api/devices/1/update/userspace`,
      watch the session in `GET /api/devices/1/updates` until
      `validated_files` covers `main.py`, then confirm the userspace
      flag flips to false after the re-report

## Notes

- No `DeviceIgnoredFile` rows need seeding for device-only files
  anymore — the original 4-row workaround (device 1: `debug_worker.py`,
  `hmac.py`, `ble_secrets.json`, `boot.py`) was never executed.
- The ignore mechanism still has value for files present on **both**
  sides where the device's version is intentional (local config/secrets
  that also live in the repo) — see the dev DB review note in the
  original version: whether `debug_worker.py`/`hmac.py` belong in the
  repo is a repo-content decision, not a code one.
