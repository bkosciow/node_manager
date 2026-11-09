# SPEC-002 — Per-Device Ignored Files

**Status**: Shipped | **Size**: M | **Backfilled**: 2026-10-28
**Implements**: `app/models/device_ignored_file.py`, `app/crud/device_ignored_file.py`, `app/schemas/device_ignored_file.py`, `ignored-files` routes in `app/rest_server.py`, and the ignore filter inside `app/crud/update_status.py`
**Original commit**: `8bd0948` "feat: add per-device ignored files, excluded from update checks" (2026-10-25)

## 1. Overview

Let an operator **exclude specific files from the update check** for a single
device, per repo type. A device may intentionally run a local override of a
file (e.g. a tuned config or a patched binary); that override makes the
device hash differ from the repo hash for that file, which would otherwise show
a perpetual "update available" on that one file.

`device_ignored_files` records `{device_id, repo_type, filename}` rows. The
update-status logic from [SPEC-001](SPEC-001-2026-10-28-device-update-status.md)
drops those filenames from the **device** side of the comparison before
deciding "update available?" or building the per-file diff. Ignoring is
scoped to one device + one repo type, so it never affects any other device.

## 2. Reference modules

- CRUD/route shape mirrors the existing per-resource pattern
  (`app/crud/device_event.py` + its routes): a data-access module re-exported
  from `app/crud/__init__.py`, validated request/response Pydantic schemas, and
  thin `rest_server.py` routes that 404 on a missing parent (`device`).
- The exclusion itself is a small filter hook into
  `app/crud/update_status.py` — the only consumer.

## 3. Data models

New table `device_ignored_files`:

| Column | Type | Notes |
|---|---|---|
| `id` | `Integer` PK, indexed | auto |
| `device_id` | `Integer`, FK → `devices.id` `ondelete CASCADE`, not null | scoped to one device |
| `repo_type` | `String(50)`, not null | `microplate` or `userspace` |
| `filename` | `String(255)`, not null | the file to skip |
| `ignored_at` | `DateTime`, default `utcnow` | when the ignore was added |

Unique constraint `uq_device_repo_filename` on
`(device_id, repo_type, filename)` — a file can be ignored at most once for a
given device + type. Registered in `app/models/__init__.py`.

Relationship: `Device.ignored_files` ↔ `DeviceIgnoredFile.device`
(`back_populates`, `cascade="all, delete-orphan"`) — deleting a device removes
its ignore rows.

## 4. Architecture

```
rest_server.py  (tags=["ignored-files"], auth = verify_token)
  GET/POST/DELETE /api/devices/{device_id}/ignored-files
        │  (404 when the device itself is missing)
        ▼
crud/device_ignored_file.py        re-exported via app/crud/__init__.py
  get_ignored_files(db, device_id)
  create_ignored_file(db, device_id, data)   -> DeviceIgnoredFile | None
  delete_ignored_file(db, device_id, repo_type, filename) -> bool
        │
        ▼
crud/update_status.py
  _get_ignored_filenames(db, device_id, repo_type) -> set[str]
  _filter_ignored(device_hashes, ignored)
```

The update path (SPEC-001) calls `_get_ignored_filenames(db, device_id,
repo_type)` then `_filter_ignored(...)` on the **device** hash dict before the
equality / diff step. Because the filter is keyed on `(device_id, repo_type)`,
an ignore in `microplate` has no effect on the `userspace` comparison.

## 5. API contracts

Auth: `verify_token`; DB: `get_db`. All routes 404 `"Device not found"` when
the `device_id` does not exist.

### `GET /api/devices/{device_id}/ignored-files`
`response_model = list[IgnoredFileResponse]`. Returns all ignore rows for the
device (across repo types).

### `POST /api/devices/{device_id}/ignored-files`
`response_model = IgnoredFileResponse`. Body `IgnoredFileCreate`:

```json
{ "repo_type": "microplate", "filename": "config.bin" }
```

- `400` (Pydantic) if `repo_type ∉ {microplate, userspace}` or `filename` is
  empty/whitespace-only (filename is stripped before persist).
- `409` when `(device_id, repo_type, filename)` is already ignored
  (duplicate ⇒ `IntegrityError` on the unique constraint, caught in the route).
- `201`-equivalent `IgnoredFileResponse` on success.

### `DELETE /api/devices/{device_id}/ignored-files?repo_type=&filename=`
Query params `repo_type` + `filename` (both required). Returns
`{"message": "File '<filename>' removed from ignored list"}`.
`404` if the specific row is not found for that device.

### Schemas (`app/schemas/device_ignored_file.py`)
- `IgnoredFileCreate`: `repo_type: str`, `filename: str` + validators
  (repo-type allow-list; filename non-empty + stripped).
- `IgnoredFileResponse`: `id, device_id, repo_type, filename, ignored_at`
  (`from_attributes`).

## 6. Behavior / edge cases (mirrored by tests)

| Case | Result |
|---|---|
| ignored file appears in device hash | excluded from both `check_update_available` and `get_repo_file_diff` |
| multiple ignored files on a device | all dropped, remaining files still diffed |
| un-ignore a file (DELETE) | that file re-enters the diff |
| file ignored under a *different* `repo_type` | no effect on the other type's comparison |
| `create` for a missing device | returns `None` → route 404 |
| duplicate `create` | `IntegrityError` → route 409 |
| `delete` of a row that doesn't exist | returns `False` → route 404 |

## 7. User stories

### Story 1 — Operator silencing a known local override
**Persona**: Field engineer who deliberately ships a patched `config.bin` to one
gateway and does not want the dashboard to keep flagging it.

1. See the noise: `GET /api/devices/7` → `assigned_repos[0].updatable_files`
   keeps listing `config.bin` because the gateway's patched hash ≠ repo hash.
   ```
   ┌──────────────────────────────────────────────┐
   │ updatable_files:  config.bin  (abc → def)    │  ← perpetual flag
   └──────────────────────────────────────────────┘
   ```
2. Silence it: `POST /api/devices/7/ignored-files`
   `{"repo_type":"microplate","filename":"config.bin"}` → 200.
   Behind the scenes: a `device_ignored_files` row is inserted; the next
   `GET /api/devices/7` drops `config.bin` from `updatable_files` (only that
   device, only `microplate`).
3. **Change vs. current state**: before, the only way to stop the flag was to
   push the patched file into the repo (polluting the shared repo) or fix the
   device. Now a per-device, per-type ignore list expresses intent without
   touching the repo.

### Story 2 — Automation that respects operator overrides
**Persona**: Deploy tooling that pushes only `updatable_files`.

1. Reuse `GET /api/devices` / `GET /api/devices/{id}` — the ignore list is
   already applied server-side, so the tool never sees ignored files and never
   re-pushes the operator's override.
2. **Comparison**: without ignores, a device running any local change
   reports `updates_available=true` forever; with per-device ignores, only
   genuinely unmanaged divergences remain actionable.

## 8. Configuration

None new. Standard `verify_token` / `get_db` dependencies; table is created by
`init_db()` / `Base.metadata.create_all` like every other model.

## 9. Testing

`tests/unit/test_ignored_files.py` — 3 groups:
`TestIgnoredFileCrud` (create/list, missing device, duplicate `IntegrityError`,
delete, delete-missing, multi-repo-type), `TestHashComparisonWithIgnored`
(excluded from diff & update check, multiple ignores, remove restores, other
repo type unaffected), and `TestIgnoredFileSchema` (valid create, invalid repo
type, empty/whitespace filename, stripping).

## Implementation Checklist

- [x] `DeviceIgnoredFile` model + `Device.ignored_files` relationship
- [x] Model registered in `app/models/__init__.py`
- [x] `IgnoredFileCreate` / `IgnoredFileResponse` schemas
- [x] CRUD `get/create/delete` + re-export
- [x] `GET/POST/DELETE /api/devices/{id}/ignored-files` routes (404/409)
- [x] update-status filter (`_get_ignored_filenames` + `_filter_ignored`)
- [x] Unit tests green (`test_ignored_files.py`)

## Changelog

### 2026-10-28
- Backfilled specification (documentation only; no code change). Gate note:
  `GUARDRAILS.md` BLOCK rules / architectural decisions still open.

### 2026-10-25
- Initial implementation (commit `8bd0948`): model + CRUD + `ignored-files`
  endpoints + exclusion from the update check.
