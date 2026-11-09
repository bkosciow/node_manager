# SPEC-001 — Device Update Status (repo ↔ device hash diff)

**Status**: Shipped | **Size**: M | **Backfilled**: 2026-10-28
**Implements**: `app/crud/update_status.py`, `app/schemas/device.py` (`UpdatesAvailable` / `DeviceWithUpdates`), wiring in `app/rest_server.py`
**Original commit**: `ed3db6b` "deetct repo <> devicre diff in hashes" (2026-06-21)

## 1. Overview

Detect whether a device has **pending repository updates** by comparing the
file-hash map the device last reported against the file hashes currently in its
assigned repository.

A device reports the SHA256 of each file it has locally as a `DeviceEvent`
whose `event_type` is `system.{repo_type}.hash` (i.e.
`system.microplate.hash` or `system.userspace.hash`) and whose `parameters` is
a `{filename: sha256}` map. The manager compares that map to the set of
`RepositoryFile.sha256` values for the repository assigned to the device and
answers two questions:

1. **Per device + repo type** — is an update available? (`bool`)
2. **Per device + repo type** — *which files* differ? (a diff list)

This is read-only: it never mutates the device or the repo; it only reads
stored event params and `RepositoryFile` rows.

## 2. Reference modules

Structurally reuses existing layers rather than introducing new storage:

- `app/models/device_event.py` — source of the device-side hash map.
- `app/models/repository.py` (`RepositoryFile.sha256`) — source of the
  repo-side hash map.
- `app/models/node_repository.py` — the `device → repository (repo_type)`
  link that scopes the comparison.

No new tables are added by this feature (the companion
[SPEC-002](SPEC-002-2026-10-28-device-ignored-files.md) adds one).

## 3. Data models

No new tables. Consumes:

| Source | Fields used | Role |
|---|---|---|
| `DeviceEvent` | `event_type = "system.{repo_type}.hash"`, `parameters` (JSON `{filename: sha256}`) | Last hash map reported by the device |
| `RepositoryFile` | `filename`, `sha256` | Authoritative hash map of the repo |
| `NodeRepository` | `device_id`, `repository_id`, `repo_type` | Which repo a device is checked against, per type |

## 4. Architecture

Single data-access module `app/crud/update_status.py`, called only by
`app/rest_server.py`. Layering follows the project standard
(Route → CRUD → ORM), no DB access in the route.

```
rest_server.py
  list_devices            → get_device_updates(db, device_id)     → {microplate: bool, userspace: bool}
  get_single_device       → get_repo_file_diff(db, device_id, repo_id, repo_type)  → [ {filename, device_hash, repo_hash} ]
                              │
                              ▼
crud/update_status.py
  get_device_updates()      # iterate the device's repo_types, delegate
     └─ check_update_available()   # dict equality (bool)
  get_repo_file_diff()      # element-wise diff (list)
     both call:
       _get_hash_dicts()   # device_hashes (dict|None) + repo_hashes (dict)
```

Key functions:

- `check_update_available(db, device_id, repository_id, repo_type) -> bool`
  True when the (post-SPEC-002-filtered) device hash dict `!=` the repo hash
  dict. **`False` when the device has never reported a hash event** (nothing to
  compare is not an update).
- `get_repo_file_diff(db, device_id, repository_id, repo_type) -> list[dict]`
  Sorted list of `{filename, device_hash, repo_hash}` for files that differ.
  `device_hash` is `None` when the file exists only in the repo; `repo_hash` is
  `None` when it exists only on the device. Empty list when the device has no
  event yet or the maps are equal.
- `get_device_updates(db, device_id) -> dict`
  Always returns `{"microplate": bool, "userspace": bool}`. A missing
  `NodeRepository` assignment for a type yields `False` for that type.

### Comparison semantics

| Device map vs repo map | update? | diff entry |
|---|---|---|
| identical dicts | no | — |
| one hash differs | yes | that file |
| file only in repo | yes | `{device_hash: None, repo_hash: <sha>}` |
| file only on device | yes | `{device_hash: <sha>, repo_hash: None}` |
| device has no event | no | empty list |
| both empty sets | no | empty list |

SPEC-002 additionally removes ignored filenames from the *device* side before
this comparison (see SPEC-002 §5).

## 5. API contracts

Auth on all routes: `token: str = Depends(verify_token)` (graceful skip when
`API_TOKEN` is empty). DB: `db: Session = Depends(get_db)`.

### `GET /api/devices` (modified)
`response_model = list[DeviceWithUpdates]`, `tags=["devices"]`.
Pagination: `skip: int = Query(0, ge=0)`, `limit: int = Query(100, ge=1, le=1000)`
(422 if `limit > 1000`).

Each item now carries `updates_available`:

```json
{
  "id": 1, "chip_id": "ABC123", "node": "sensor-1",
  "created_at": "2026-06-21T10:00:00",
  "updates_available": { "microplate": true, "userspace": false }
}
```

The route computes `get_device_updates()` for **every** device on the page
(one query group per device).

### `GET /api/devices/{device_id}` (modified)
`device_id: int = Path(ge=1)`; 404 `"Device not found"` when absent.
Hand-built dict (project standard: raw data, no envelope):

```json
{
  "id": 1, "chip_id": "ABC123", "node": "sensor-1",
  "created_at": "2026-06-21T10:00:00",
  "events": { "system.microplate.hash": { "core.bin": "abc…" } },
  "assigned_repos": [
    {
      "id": 1, "repository_id": 7, "repository_name": "fw",
      "repo_type": "microplate", "assigned_at": "2026-06-21T10:05:00",
      "updatable_files": [
        { "filename": "core.bin", "device_hash": "abc", "repo_hash": "def" }
      ]
    }
  ]
}
```

`updatable_files` per assignment = `get_repo_file_diff(...)`.

## 6. User stories

*API-only feature — no UI; "wireframes" are request/response traces.*

### Story 1 — Operator triaging which nodes need a deploy
**Persona**: Fleet operator, no engineering background, checking from a
dashboard poller that reads `GET /api/devices`.

1. **Dashboard poll** — `GET /api/devices?limit=1000`.
   ```
   ┌────────────────────────────────────────────┐
   │ sensor-1  updates_available: MP ✓  US ✗   │  ← poller surfaces the flag
   │ sensor-2  updates_available: MP ✗  US ✗   │
   └────────────────────────────────────────────┘
   ```
   Behind the scenes: for each device, `get_device_updates()` reads the two hash
   events and the two assigned repos, and returns the two booleans. Devices with
   no assignment or no reported hash show `false` (not "unknown" — the schema is
   a plain bool, so "no data yet" reads as "no update").

2. **Drill-down** — `GET /api/devices/1` to see *why* `microplate` is `true`.
   Behind the scenes: `updatable_files` lists the specific files whose hashes
   diverge, so the operator can confirm it is a real change, not a stale event.

### Story 2 — Integrator wanting a machine-readable diff
**Persona**: Automation engineer polling a single node to decide what to push.

1. `GET /api/devices/42` and read `assigned_repos[].updatable_files`.
2. **Change vs. current state**: before this feature the endpoint returned
   `events` + `assigned_repos` **without** `updatable_files`; the caller had to
   diff `events["system.*.hash"]` against a separate `GET /api/repos` call
   itself. Now the diff is returned server-side, per assignment.
3. `device_hash == null` ⇒ "device lacks this file → push it";
   `repo_hash == null` ⇒ "device has a stray file" (informational);
   both present and unequal ⇒ "file changed → redeploy".

## 7. Configuration

None new. Uses the standard `verify_token` / `get_db` dependencies and the
`API_TOKEN`-gated auth already documented in `.ai/standards/api/auth.md`.

## 8. Testing

`tests/unit/test_update_status.py` — 15 tests across
`TestCheckUpdateAvailable`, `TestGetDeviceUpdates`, `TestGetRepoFileDiff`,
covering match / differ / one-sided files / no-event / empty-sets / both repo
types / sorted multi-diff. Response-shape integration coverage lives in
`tests/integration/test_device_api.py`.

## Implementation Checklist

- [x] `check_update_available`, `get_repo_file_diff`, `get_device_updates` in `app/crud/update_status.py`
- [x] Re-export from `app/crud/__init__.py`
- [x] `UpdatesAvailable` + `DeviceWithUpdates` schemas in `app/schemas/device.py`
- [x] `GET /api/devices` returns `list[DeviceWithUpdates]`
- [x] `GET /api/devices/{id}` adds `updatable_files` per assigned repo
- [x] Unit tests green (`test_update_status.py`)

## Changelog

### 2026-10-28
- Backfilled specification (documentation only; no code change). Gate note:
  `GUARDRAILS.md` BLOCK rules / architectural decisions still open.

### 2026-06-21
- Initial implementation (commit `ed3db6b`): `update_status` CRUD module,
  `UpdatesAvailable`/`DeviceWithUpdates` schemas, and endpoint wiring in
  `rest_server.py`.
