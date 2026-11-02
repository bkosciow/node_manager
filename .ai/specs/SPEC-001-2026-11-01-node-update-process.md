# SPEC-001 — Node Update Process

## Overview

Operator-triggered firmware/userspace upgrade for a device. When the repo hash
diff for a device's assigned repository is non-empty (microplate or userspace),
an operator can start the upgrade process:

1. The API verifies the diff exists (repo-side files only — see
   "Device-only diff entries" in the API section) and creates an
   **upgrade session** (`NodeUpdate`, uuid token).
2. The server broadcasts a `system.files.upgrade` UDP message to the device,
   carrying `base_url` (upgrade-session URL), the list of changed `files`, and
   the upgrade `type`.
3. The device (ESP) reboots, downloads each file from
   `<base_url>/get/<filename>`, SHA-256s it, and POSTs to
   `<base_url>/validate/<filename>`.
4. On success the device moves files into place (`/` for userspace,
   `/microplate/` for microplate) and reboots; it then re-reports its hashes
   via the existing `system.{repo_type}.hash` discovery event, which clears
   the diff.

**Test node:** chip_id `node-north-001`.

**What already exists (do not rebuild):**
- Hash diff: `app/crud/update_status.py` — `get_repo_file_diff`,
  `check_update_available`, `get_device_updates` (compares
  `DeviceEvent system.{repo_type}.hash` JSON params vs `RepositoryFile.sha256`,
  excluding `DeviceIgnoredFile`). The flag is **repo-driven**:
  `check_update_available` only counts files that exist in the repo
  (missing or hash-differing on the device); device-only files never set
  `updates_available` — see "Device-only diff entries".
- Device discovery + hash reporting: `app/message_handler/device_discovery.py`.
- Repo sync from disk: `repo_scanner.py` → `upgrades/<repo>/{_microplate,_userspace}/`.
- UDP broadcast sender: `app/services/comm.py` (`comm.send`); bootstrap pattern
  in `ping_node_north.py` (address, optional AESSHA1 cryptor, Message identity).

**What this spec adds:** trigger endpoint, `NodeUpdate` session model/CRUD,
file-serve + validate endpoints, fetch/validate tracking, and a
per-device session listing endpoint.

## Reference

| Reference | Why |
|---|---|
| Old MVP `node_manager/api/routes.py`, section "UPDATE NODES ROUTES" (`/home/kosci/old_services/node_manager/`) | The original trigger/serve/validate design this ports; status-code semantics are kept (404 nothing-to-update, uuid-token scoping, 400 on hash mismatch) — the 400 response payload is reshaped (drops the old `"error"` key, adds `valid`/hash fields, per the API table below) |
| `upgrades/node_north/_microplate/upgrade.py` + `upgrade_handler.py` | The frozen ESP-side contract — see "ESP Contract" below. Node code must keep working unchanged |
| `ping_node_north.py` | Exact `comm` bootstrap pattern (address, cryptor, Message identity) to lift into the FastAPI app |

## User Stories

### Story 1 — Happy path: operator updates node-north-001

> **Persona**: Bartek — the site owner. Has pushed new userspace files into
> `upgrades/node_north/_userspace/` and run `repo_scanner.py`. Wants the live
> node `node-north-001` to pick them up.

**Step 1 — see what's pending**

```
$ curl -H "Authorization: Bearer $TOKEN" localhost:8577/api/devices
[{"chip_id": "node-north-001", "node": "node-north", ...,
  "updates_available": {"microplate": false, "userspace": true}}]
```

> **Behind the scenes**: `GET /api/devices` already computes
> `updates_available` per device via `get_device_updates`.

**Step 2 — trigger the upgrade**

```
$ curl -X POST -H "Authorization: Bearer $TOKEN" \
    localhost:8577/api/devices/1/update/userspace
HTTP 202
{"message": "Upgrade broadcast sent", "token": "3f9c…", "files": ["config.py", "main.py"]}
```

> **Behind the scenes**: diff is non-empty → a `NodeUpdate` row is created with
> a fresh uuid token and the repo-side diff's filenames. A
> `system.files.upgrade`
> message is broadcast on 5053/UDP targeted at the device's `node` name. The
> node writes params to `/.upgrade.json` and reboots.

**Step 3 — watch it happen**

```
$ curl -H "Authorization: Bearer $TOKEN" localhost:8577/api/devices/1/updates
[{"token": "3f9c…", "repo_type": "userspace",
  "files": ["config.py", "main.py"],
  "fetched_files": ["config.py", "main.py"],
  "validated_files": ["config.py", "main.py"],
  "created_at": "...", "updated_at": "..."}]
```

> **Behind the scenes**: each node download hits
> `GET /api/update/{token}/get/<file>` (recorded in `fetched_files`); each
> hash POST hits `POST /api/update/{token}/validate/<file>` (recorded in
> `validated_files`). The node moves files to `/` and reboots.

**Step 4 — verify completion**

After reboot, discovery re-runs on the node; `system.userspace.hash` event
now matches the repo → `updates_available.userspace` flips to `false`.

> **Change vs. current state**: Steps 2–3 don't exist yet (no trigger, no
> serve/validate endpoints, no session tracking). Steps 1 and 4 already work.

### Story 2 — Alternative: nothing to update / unassigned

> **Persona**: Bartek, again, but the repo hasn't changed since last scan —
> or he types the repo type wrong.

```
# No diff:
$ curl -X POST .../api/devices/1/update/microplate
HTTP 404 {"detail": "Nothing to update"}

# Device has no microplate repo assigned:
$ curl -X POST .../api/devices/1/update/microplate
HTTP 404 {"detail": "No microplate repository assigned to this device"}

# Unknown repo type:
$ curl -X POST .../api/devices/1/update/firmware
HTTP 400 {"detail": "Invalid repository type"}

# Diff consists only of device-only files (repo knows nothing about them):
$ curl -X POST .../api/devices/1/update/userspace
HTTP 404 {"detail": "Nothing to update"}   # an upgrade can never remove device-only files
```

> **Behind the scenes**: 400/404 checks happen in order: repo_type validity
> → device existence → repo assignment → diff. No session created, nothing
> broadcast.

> **Change vs. current state**: None of these paths exist today; all new.

### Story 3 — Edge case: corrupt download mid-upgrade

> **Persona**: Bartek, watching the session. A flaky WiFi link corrupts one
> download on the node.

Node downloads `config.py` fine (validated), then `main.py` fails its
hash check:

```
$ curl .../api/devices/1/updates
[{"token": "3f9c…", "files": ["config.py", "main.py"],
  "fetched_files": ["config.py", "main.py"],
  "validated_files": ["config.py"], ...}]
```

> **Behind the scenes**: the node prints "HASH FAILED - UPGRADE ABORTED",
> aborts the upgrade (files are never moved into place), and reboots back
> into normal userspace. The session stays permanently in-progress:
> `validated_files` ⊂ `files`. The diff still shows on the next
> `GET /api/devices`, so the operator just triggers the upgrade again.

> **Change vs. current state**: Today a failed upgrade leaves no trace. After
> this change, the session record shows exactly where it stopped.

## Architecture

```
 operator ──POST /api/devices/{id}/update/{repo_type}──▶ rest_server (auth)
                                                          │
   diff gate (update_status.get_repo_file_diff)           │ 404 no diff
                                                          ▼
                                            create NodeUpdate (uuid token)
                                                          │
                     comm.send(system.files.upgrade) ─────┘
                              │  UDP 5053/UDP broadcast, targets=[device.node]
                              ▼
                     ESP node: /.upgrade.json, reboot
                              │  GET  <base_url>/get/<file>       (public, token-scoped)
                              │  POST <base_url>/validate/<file>  (public, token-scoped)
                              ▼
                     file move + reboot + re-report hashes (system.{type}.hash)
```

New components:

1. **Model** `NodeUpdate` (`app/models/node_update.py`) + schema
   `app/schemas/node_update.py` + CRUD `app/crud/node_update.py` — the
   upgrade session. Registered in `models/__init__.py` and
   `crud/__init__.py`.
2. **Trigger route** in `app/rest_server.py` — auth'd, diff-gated
   (repo-side diff only: entries with `repo_hash` not null), creates
   the session, broadcasts.
3. **Serve / validate routes** in `app/rest_server.py` — public
   (no `verify_token`). The `api/auth` standard says "`/health` is public
   (no auth) — other public endpoints may exist but are rare" and bypasses
   need an explicit reason; ours: the ESP node has no API token, so
   access is scoped by the unguessable uuid + the session's `files`
   allow-list.
4. **Tracking** — serve/validate CRUD methods append to `fetched_files` /
   `validated_files` on the session row; `GET /api/devices/{id}/updates`
   exposes them.
5. **IoT bootstrap helper** — extract `app/services/iot_bootstrap.py`
   (prescribed by `.ai/standards/messaging/iot-bootstrap.md`, not yet in
   code): `bootstrap(send_to: tuple | None = None)` performing, in order —
   1. `logging.basicConfig(level=logging.INFO)`,
   2. optional AESSHA1 cryptor (only when `settings.sl_passphrase` is
      set; registered on BOTH `Message.add_decoder` and
      `Message.add_encoder` — the iot_message library is process-global),
   3. identity `Message.node_name`/`Message.chip_id` from settings,
   4. `comm.address = send_to` when provided.
   FastAPI startup calls
   `bootstrap(send_to=(settings.node_listener, int(settings.node_listener_port)))`
   when `settings.node_listener` is set, else `bootstrap()` (listener-only
   form; `comm.address` stays unset). If the node listener is unconfigured
   at trigger time, the trigger returns 503. Do NOT extend the copy-pasted
   preambles in existing scripts — the helper is the only blessed
   preamble (`iot-bootstrap` standard: "when touching them, refactor to
   the helper; don't extend the copy-paste").

### ESP Contract (frozen)

The node side (`upgrades/node_north/_microplate/`) is written and deployed;
the server must match it exactly:

| Element | Contract |
|---|---|
| Event | `system.files.upgrade` in the broadcast message |
| Targets | `[device.node]` (device name, same as old MVP) |
| Parameters | `type` ∈ {"userspace", "microplate"}, `files` (list of filenames — only the diff), `base_url` (no trailing slash) |
| File download | `GET <base_url>/get/<filename>` → 200 + file bytes; node reboots after writing params and aborts the whole upgrade on any non-200 |
| Hash check | `POST <base_url>/validate/<filename>` body `{"hash": "<sha256 hex>"}` → 200 on match; **any** non-200 aborts the upgrade (node reboots clean, old code stays) |
| Apply | userspace → `/`, microplate → `/microplate/`; then `machine.reset()` |
| Re-report | after reboot the node re-runs discovery and sends `system.{type}.hash` with new file hashes, clearing the diff |

## Data Models

### New: `NodeUpdate` (`app/models/node_update.py`)

```python
class NodeUpdate(Base):
    __tablename__ = "node_updates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token: Mapped[str] = mapped_column(String(36), nullable=False)
    device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    repository_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False)
    repo_type: Mapped[str] = mapped_column(String(50), nullable=False)
    files: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    fetched_files: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    validated_files: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("token", name="uq_node_update_token"),
    )
```

- `files`: the **repo-side** diff filenames at trigger time
  (diff entries with `repo_hash` not null; device-only entries excluded —
  see "Device-only diff entries" below) — this is also the
  **allow-list** for the get/validate endpoints (a request for a file not in
  this list → 404).
- `token`: `str(uuid4())`, generated in the route, passed to CRUD.
  Uniqueness lives in the named `uq_node_update_token`
  `UniqueConstraint` in `__table_args__` (`query-style` standard — no
  inline `unique=True`).
- Relationships: `device` (`Device`, back_populates `updates`),
  `repository` (`Repository`, back_populates `updates`).
  Add `updates` relationships on `Device` and `Repository`
  (`cascade="all, delete-orphan"` on the Device side).

### Schemas (`app/schemas/node_update.py`)

- `NodeUpdateCreate` — `token`, `device_id`, `repository_id`, `repo_type`,
  `files: list[str]` (validators: non-empty files, valid repo_type)
- `NodeUpdateResponse` — all persisted fields (no Create inheritance,
  per schema standard), `model_config = {"from_attributes": True}` so
  `GET /api/devices/{id}/updates` can return ORM rows via `response_model`
- `UpdateValidateRequest` — `hash: str`

### CRUD (`app/crud/node_update.py`)

| Function | Signature | Returns |
|---|---|---|
| create | `create_node_update(db, data: NodeUpdateCreate)` | `NodeUpdate` |
| get by token | `get_node_update_by_token(db, token: str)` | `NodeUpdate | None` |
| list per device | `list_node_updates(db, device_id: int)` | `list[NodeUpdate]` (created_at desc, `id` desc tiebreaker) |
| record fetch | `record_fetched_file(db, token, filename)` | `NodeUpdate | None` |
| record validate | `record_validated_file(db, token, filename)` | `NodeUpdate | None` |

Record methods append (dedup), commit, refresh. CRUD owns commits
(`session-commit` standard).

Query style: all functions in this new CRUD file use SQLAlchemy 2.0-style
`select()` (`query-style` standard); the legacy `db.query()` idiom
elsewhere is debt, not a style to copy.

## API Contracts

Base: current API. `base_url` = `settings.base_url` if set, else
`http://{settings.app_host}:{settings.app_port}`.

### `POST /api/devices/{device_id}/update/{repo_type}` — trigger (auth'd)

Check order and responses:

| Condition | Response |
|---|---|
| `repo_type` not in {`microplate`, `userspace`} | 400 `{"detail": "Invalid repository type"}` |
| Device not found | 404 `{"detail": "Device not found"}` |
| No `NodeRepository` for this device + repo_type | 404 `{"detail": "No {repo_type} repository assigned to this device"}` |
| No repo-side diff: `get_repo_file_diff` → `[]`, or every entry has `repo_hash` = null (device-only files only) | 404 `{"detail": "Nothing to update"}` |
| Node listener unconfigured (`settings.node_listener` empty) | 503 `{"detail": "Node listener not configured"}` |
| Success: session created + broadcast | 202 `{"message": "Upgrade broadcast sent", "token": "<uuid>", "files": [...]}` |

Message sent:

```python
{
    "event": "system.files.upgrade",
    "targets": [device.node],
    "parameters": {
        "type": repo_type,
        "files": [d["filename"] for d in diff if d["repo_hash"] is not None],
        "base_url": f"{base_url}/api/update/{token}",
    },
}
```

Concurrent triggers: there is no uniqueness constraint on
`(device_id, repo_type)` — multiple sessions coexist (Story 3 sanctions
re-triggering). Each broadcast just overwrites the node's
`/.upgrade.json`, so the node follows the most recent trigger; older
sessions remain as history records. No auto-cleanup in v1.

Device-only diff entries: `get_repo_file_diff` computes over the UNION of
device and repo filenames, so entries with `repo_hash` = null (file exists
on the device but not in the repo — e.g. the ESP's `error` key from a
failed hash scan, or stray root-level userspace files) appear in the raw
diff. They are EXCLUDED from the trigger: an upgrade pushes repo state to
the device and can never remove a file the repo doesn't know about (the
old MVP iterated repo files only — `_return_hash_diff` in
`service/microplate.py`). Including them would make the ESP 404 on `get`
and abort the whole upgrade, permanently — re-triggering cannot fix it.
Consequences:

- `NodeUpdate.files` (the get/validate allow-list) holds filtered names only
- the `updates_available` flag is computed the same asymmetric way
  (`check_update_available` iterates repo files only), so a diff that
  consists solely of device-only entries shows **no** update flag; the
  entries remain visible in the device detail's `updatable_files` as
  information. The operator clears that state by removing the stray file
  on the device (or fixing the failed hash scan) and letting discovery
  re-report

### `GET /api/update/{token}/get/{filename}` — file serve (public)

| Condition | Response |
|---|---|
| Unknown token | 404 `{"detail": "Upgrade not found"}` |
| Filename not in session's `files` | 404 `{"detail": "File not part of this upgrade"}` |
| No `RepositoryFile` record, or file missing on disk | 404 `{"detail": "File not found"}` |
| Success | 200, `FileResponse` (octet-stream, as attachment). Appends filename to `fetched_files`. |

Physical path: `{settings.upgrades_dir}/{repository.name}/_{repo_type}/{filename}`
— the same layout `repo_scanner.py` walks (`REPO_TYPE_MAP` inverse:
`_microplate` / `_userspace`).

### `POST /api/update/{token}/validate/{filename}` — hash check (public)

Body: `{"hash": "<sha256 hex>"}`

| Condition | Response |
|---|---|
| Unknown token / file not in session | 404 (same as get) |
| No `RepositoryFile` record for the filename (e.g. re-scanned out of the repo after the session was created) | 404 `{"detail": "Hash not found"}` |
| Hash matches `RepositoryFile.sha256` | 200 `{"valid": true}` — appends filename to `validated_files` |
| Mismatch | 400 `{"valid": false, "received_hash": ..., "expected_hash": ...}` |

### `GET /api/devices/{device_id}/updates` — sessions (auth'd)

- 404 if device missing; otherwise `list[NodeUpdateResponse]`, newest first.
- This is the "in-progress upgrades" view (Story 1 step 3, Story 3).

## Configuration

New fields in `app/config.py` (all with defaults, `.env`-overridable).
Per the `config-settings` standard ("adding a new settings field: add it
to Settings and document it in `.env.example`"), both are also added to
`.env.example`:

| Setting | Default | Meaning |
|---|---|---|
| `upgrades_dir` | `"./upgrades"` | Root of repo folders on disk for the FastAPI serve path. Note: `repo_scanner.py` currently hardcodes `UPGRADES_DIR = "./upgrades"` and does NOT read this setting — until the scanner is also migrated, the setting governs only the serve path, so it must match the volume mapping the scanner uses |
| `base_url` | `""` | Publicly reachable base URL of this API for `base_url` in the upgrade message; empty → derive `http://{app_host}:{app_port}` |

`.env.example` changes: add `UPGRADES_DIR=./upgrades` and `BASE_URL=`,
plus the missing `NODE_LISTENER=` line (today only `NODE_LISTENER_PORT`
is documented, and `NODE_LISTENER` is part of the 503 gate).

Compose wiring — without it the trigger is a permanent 503 in compose
deployments, and the derived base URL (`http://0.0.0.0:9092`) is
unreachable from the nodes. Add to the `api` service in BOTH
`docker-compose.yml` and `docker-compose.prod.yml` (following the
existing `${VAR:-}` interpolation pattern):

```yaml
      - NODE_LISTENER=${NODE_LISTENER:-}      # host address nodes reach the broadcast on (host-network mode: host's LAN IP)
      - BASE_URL=${BASE_URL:-}                # URL nodes use to fetch files; must be reachable from the ESP (e.g. http://192.168.x.x:9092)
      - UPGRADES_DIR=${UPGRADES_DIR:-./upgrades}
```

Note: the repo folders reach the api container via the Dockerfile's
`COPY . .` (baked into the image; no upgrades volume mount today) — so
changing repo files in a compose deployment requires a rebuild unless an
upgrades volume is added.

Reused as-is: `node_listener`, `node_listener_port` (broadcast target),
`sl_statisiv`/`sl_ivkey`/`sl_datakey`/`sl_passphrase` (AES/SHA1 when
`sl_passphrase` is set), `api_token`, `node_name`, `node_id`.

## Testing & Verification

- **Unit** (`tests/unit/test_node_update_crud.py`): create, get-by-token,
  record_fetched/validated dedup + commit/refresh idiom, one class per
  CRUD fn (per `testing/unit-test-idiom`).
- **Integration** (`tests/integration/`):
  - trigger: seed device + NodeRepository + RepositoryFile + a
    `system.userspace.hash` event with a diff; monkeypatch
    `comm.send` AND set `settings.node_listener` to a dummy address
    (the default `""` would trip the 503 gate before any send); assert
    202 + session row + exact message payload; assert 404
    nothing-to-update, 400 invalid repo_type, and 503 with
    `settings.node_listener` left empty. Seed a device-only diff entry
    (a filename in the hash event with no `RepositoryFile` record) and
    assert it is excluded from the broadcast payload and from
    `NodeUpdate.files`; assert 404 nothing-to-update when the diff
    consists of device-only entries only.
  - serve/validate: create a session, write a temp file into
    `upgrades_dir` fixture; GET returns bytes + records fetch; POST with
    good hash → 200 + recorded, bad hash → 400 with payload; foreign
    filename → 404.
- **Manual (test node `node-north-001`)**: run dev server +
  `device_scaner.py` + `repo_scanner.py`; change a `_userspace` file;
  `POST /api/devices/{id}/update/userspace`; watch ESP serial log
  ("Rebooting for the upgrade" → "Files OK - replacing userspace files" →
  reboot); confirm `GET /api/devices` shows `updates_available` cleared and
  `GET /api/devices/{id}/updates` shows the session fully validated.

## Implementation Checklist
- [x] 1. Inject standards
- [x] 2. Config fields: `upgrades_dir`, `base_url` (`app/config.py`)
- [x] 3. Deployment wiring: `.env.example` + compose env lines (both files)
- [x] 4. Model: `NodeUpdate` (+ `updates` relationships, `models/__init__.py`)
- [x] 5. Schemas: `app/schemas/node_update.py`
- [x] 6. CRUD: `app/crud/node_update.py` (+ `crud/__init__.py` re-export)
- [x] 7. IOT bootstrap helper (`app/services/iot_bootstrap.py`) + FastAPI startup wiring
- [x] 8. Trigger route: `POST /api/devices/{device_id}/update/{repo_type}`
- [x] 9. Serve/validate routes: `GET/POST /api/update/{token}/...` (public)
- [x] 10. Listing route: `GET /api/devices/{device_id}/updates`
- [x] 11. Unit tests: `tests/unit/test_node_update_crud.py`
- [x] 12. Integration tests: trigger, serve/validate, device-only, 503
- [x] 13. Verify: `/verify-standards`, lint, test run, build
- [ ] 14. Manual verification on node-north-001 (operator step)
- [x] 15. Sync spec: checklist status, review section, lessons

## Implementation Review (2026-11-02)

**Files touched**

- New: `app/models/node_update.py`, `app/schemas/node_update.py`,
  `app/crud/node_update.py`, `app/services/iot_bootstrap.py`,
  `tests/unit/test_node_update_crud.py`,
  `tests/integration/test_node_update_api.py`
- Modified: `app/config.py` (`upgrades_dir`, `base_url`),
  `app/models/{device,repository,__init__}.py` (`updates` relationships +
  registration), `app/crud/__init__.py` (re-exports),
  `app/db/session.py` (model import for `create_all`),
  `app/rest_server.py` (imports, startup bootstrap wiring, 4 routes,
  `get_repository` hoisted to top level), `.env.example`,
  `docker-compose.yml`, `docker-compose.prod.yml`

**Verification results**

- `pytest tests/` → 220 passed (46 new: 22 unit, 24 integration)
- `flake8 app/ tests/` → 0 issues
- Build import check (`from app.rest_server import app`) → 18 routes
- `/verify-standards`: 13 standards pass; 4 deviations resolved:
  1. `api/route-params` — body param sits after path params, before `db`
     (codebase majority: `assign_repo`, `add_ignored_file`). Standard +
     index.yml updated to match.
  2. Public get/validate routes — `# Exception:` comments added above
     both routes (documented api/auth deviation: nodes hold no token;
     uuid + files allow-list scoping).
  3. `testing/unit-test-idiom` — `db_session` fixture is the current
     CRUD-test convention; standard updated to mark `next(_session())`
     as legacy.
  4. `global/logging-apprise` — `iot_bootstrap.py` has no module logger;
     not applicable (module emits no logs; `comm.py` precedent).

**Implementation notes**

- Trigger's 404 gate and the broadcast `files` list both filter the
  union diff to repo-side entries (`repo_hash is not None`) — see
  "Device-only diff entries" in API Contracts.
- `validate` body param declared as `body: UpdateValidateRequest = ...`
  (Ellipsis default) — bare required body after defaulted params is a
  Python SyntaxError; matches the codebase's `= ...` convention.
- `comm.send` is gated on `settings.node_listener` (503) — matches
  `udp-topology`: unset `comm.address` would raise.

## Changelog

### 2026-11-02
- Flag semantics fix: `check_update_available` is now repo-driven —
  device-only files (e.g. node-local `boot.py`, secrets) no longer set
  `updates_available`; they remain informational in `get_repo_file_diff`
  and stay excluded from the upgrade trigger. Ignored files are now
  filtered from both sides of the comparison (previously an ignored
  file present on both sides still set the flag and would have been
  pushed by the trigger). Quick spec 001 re-scoped from manual
  `DeviceIgnoredFile` seeding to this code fix.

### 2026-11-02
- Implemented (tasks 2–13): model/schemas/CRUD/session tracking,
  iot_bootstrap helper + startup wiring, trigger/serve/validate/list
  routes, unit + integration tests; standards `api/route-params` and
  `testing/unit-test-idiom` updated after `/verify-standards`;
  device-only diff trap captured in `.ai/lessons.md`. Task 14
  (manual verification on node-north-001) remains open.

## Changelog

### 2026-11-01
- Spec-review pass: trigger now filters the diff to repo-side entries
  (device-only entries excluded — they would permanently deadlock
  upgrades), `uq_node_update_token` named constraint, `select()` CRUD
  style, real userspace filenames in stories, compose + `.env.example`
  wiring (NODE_LISTENER/BASE_URL/UPGRADES_DIR)

### 2026-11-01
- Initial specification
