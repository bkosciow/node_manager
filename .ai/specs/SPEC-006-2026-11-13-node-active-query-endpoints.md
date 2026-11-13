# SPEC-006 — Node Active Query Endpoints

## 1. Overview

Two new REST endpoints on the node_manager REST API that let the manager
**actively ask a device for fresh data**:

| Endpoint | UDP event sent | Node's reply (already ingested) |
|---|---|---|
| `POST /api/devices/{device_id}/ping` | `system.ping` | `system.pong` |
| `POST /api/devices/{device_id}/rescan/{repo_type}` | `system.{repo_type}.get_hash` (`repo_type` ∈ `microplate`, `userspace`) | `system.{repo_type}.hash` |

Together with the existing passive discovery, these are the three ways the
manager actively asks a node for data: ping, microplate rescan, userspace
rescan.

The receive side needs **no changes**: the node's replies
(`system.pong`, `system.microplate.hash`, `system.userspace.hash`) are
already parsed by the UDP listener / `device_discovery` handler and persisted
as `DeviceEvent` rows. Only the send path (new REST routes → `comm.send`)
is added.

Explicit decisions:

- **Two routes, three actions** — ping is its own route; rescan is
  parameterized by `repo_type`, mirroring the existing
  `POST /api/devices/{device_id}/update/{repo_type}`.
- **No repository assignment required** — any device can be pinged or asked
  to re-hash. This differs from `/update`, which 404s without an
  assignment, because get_hash carries no file diff and no upgrade
  session.
- **Payload has no `parameters` key** — exactly the event + targets the
  node protocol expects.

## 2. User Stories

### Story 1 — Operator checks whether a node is reachable

> **Persona**: On-call operator. Goal: find out whether `node-north` is
> alive before investigating a stuck device update. Comfortable with
> `curl` and the existing REST API.

**Step 1 — Send the ping**

```
POST /api/devices/12/ping
Authorization: Bearer <api_token>
```

→ `202 Accepted`

```json
{
  "message": "Ping broadcast sent",
  "event": "system.ping",
  "target": "node-north"
}
```

> **Behind the scenes**: route validates the device exists (404 otherwise),
> checks `settings.node_listener` is configured (503 otherwise), then
> `comm.send({"event": "system.ping", "targets": [device.node]})` — a UDP
> broadcast to `NODE_LISTENER:NODE_LISTENER_PORT` (5053 by default). The
> node answers with `system.pong`; the listener upserts a `DeviceEvent`
> row and bumps `last_seen_at` (SPEC-003).

**Step 2 — Confirm the reply**

```
GET /api/devices/12           -> fresh last_seen_at
GET /api/devices/12/events    -> system.pong event in the event map
```

`last_seen_at` comes from the device detail response (SPEC-003); the
`system.pong` event is visible in the device's event log.

> **Behind the scenes**: the listener upserted the `DeviceEvent` row and
> refreshed `last_seen_at` when the pong was ingested.

> **Change vs. current state**: Today, liveness is only inferred passively
> from `last_seen_at`, or the operator runs the standalone
> `ping_node_north.py` CLI script — which hardcodes one node name and must
> be run manually on the manager host. After this change: per-device ping
> through the authenticated API, no manual script run.

### Story 2 — Automation forces a fresh hash before an update

> **Persona**: CI / deployment job (programmatic client). Goal: verify the
> on-device file state of a device's userspace repository before pushing a
> new upgrade, so the update-diff (SPEC-003) is computed against current
> data, not a stale periodic report.

**Step 1 — Ask the node to re-hash**

```
POST /api/devices/12/rescan/userspace
Authorization: Bearer <api_token>
```

→ `202 Accepted`

```json
{
  "message": "Rescan broadcast sent",
  "event": "system.userspace.get_hash",
  "target": "node-north"
}
```

> **Behind the scenes**: `repo_type` is validated against
> `VALID_REPO_TYPES` (400 on unknown type), device existence checked
> (404), listener configured (503), then
> `comm.send({"event": "system.userspace.get_hash", "targets": [device.node]})`.
> The node re-hashes its local userspace files and broadcasts
> `system.userspace.hash` with the file→sha256 map. The listener upserts
> the `DeviceEvent` row — the same row the update-diff engine reads.

**Step 2 — Decide on the update**

The job polls `GET /api/devices/12` (its `updates_available` diff) and
triggers `POST /api/devices/12/update/userspace` only when the diff is
meaningful.

> **Change vs. current state**: Today there is **no way** to make a node
> report hashes on demand — `system.*.hash` events only arrive passively
> (node-initiated reports ingested by the UDP listener), and the
> manager-side auto-scan (SPEC-004) re-hashes the manager's own disk
> repos, not devices. Operators wait for the next node report, or run
> ad-hoc scripts. After this change: `POST .../rescan/{repo_type}` works
> for any device, with or without a repository of that type assigned (the
> node simply reports what it has).

## 3. Architecture

```
REST client ──POST──▶ FastAPI route (rest_server.py)
                              │  guards: 404 device / 400 repo_type / 503 no listener
                              ▼
                     comm.send(payload)          (app/services/comm.py, address set
                              │                   by iot_bootstrap at startup)
                              ▼  UDP 5053 broadcast
                            node ──system.pong / system.{type}.hash──▶ UDP listener
                                                                              │
   REST client ──GET──▶ /api/devices/{id}, /events ◀── DeviceEvent row ◀────┘
```

- **Reference module**: `trigger_device_update`
  (`app/rest_server.py`) — same section of the router, same guard
  structure (device 404 → `settings.node_listener` 503 → `comm.send` →
  202). The new routes deliberately **omit** its assignment lookup and
  NodeUpdate session creation.
- **Reuse, no new services**: `app.services.comm.send`,
  `app.schemas.repository.VALID_REPO_TYPES`, `iot_bootstrap` unchanged.
- **No receive-side changes**: reply events are in
  `SUPPORTED_EVENTS` (`app/message_handler/device_discovery.py`).
- **Testing**: new integration file `tests/integration/test_node_query_api.py`
  following the `test_node_update_api.py` pattern — `monkeypatch.setattr`
  on `settings.node_listener` and `comm.send` (capture payload list).
  Status branches per endpoint: ping → 202/404/503; rescan →
  202/400/404/503 (400 belongs to rescan only — it has a `repo_type`).
  Assert **full-dict equality** of each captured payload against the exact
  `{"event": ..., "targets": [...]}` dict from §5 — the *absence* of the
  `parameters` key is part of the assertion. Copy the guard order from
  `/update`, but **omit** its assignment lookup and NodeUpdate session
  creation (repeated here on purpose — "mirror /update" means the guards
  only).
- **Docs**: `README.md` keeps an endpoint table — add two rows. `docs/api.md`
  documents endpoints as `### METHOD /path` sections — add a new
  `## Device Active Query` section with two subsections, after
  `## Device Events`.

## 4. Data Models

No schema changes. No Alembic revision (SPEC-005 rule: no model change ⇒
no migration).

Relevant existing entities, for reference:

- `DeviceEvent` — stores the reply events (`system.pong`,
  `system.microplate.hash`, `system.userspace.hash`) with their JSON
  parameter maps.
- `Device.last_seen_at` / `last_updated_at` (SPEC-003) — refreshed by the
  listener when replies arrive, which is how a successful ping is observed.

## 5. API Contracts

All endpoints require the bearer API token (`Depends(verify_token)`).

### `POST /api/devices/{device_id}/ping`

| | |
|---|---|
| Path params | `device_id: int` (≥ 1) |
| Request body | none |
| OpenAPI tag | `tags=["device-queries"]` |
| Success | `202` `{"message": "Ping broadcast sent", "event": "system.ping", "target": "<device.node>"}` |
| Errors | `404` "Device not found" · `503` "Node listener not configured" |
| UDP payload | `{"event": "system.ping", "targets": [device.node]}` |

### `POST /api/devices/{device_id}/rescan/{repo_type}`

| | |
|---|---|
| Path params | `device_id: int` (≥ 1), `repo_type: str` |
| Request body | none |
| OpenAPI tag | `tags=["device-queries"]` |
| Success | `202` `{"message": "Rescan broadcast sent", "event": "system.<repo_type>.get_hash", "target": "<device.node>"}` |
| Errors | `400` "Invalid repository type" (not in `VALID_REPO_TYPES`) · `404` "Device not found" · `503` "Node listener not configured" |
| UDP payload | `{"event": "system.<repo_type>.get_hash", "targets": [device.node]}` |

Guard order mirrors `/update`: repo_type validation first (400), then
device lookup (404), then listener check (503).

**Implementation notes (pinned):**

- **Response bodies are hand-built dicts, no new Pydantic class** — the
  `api/response-format` standard prescribes "POST success: return a
  `{\"message\": \"...\"}` dict" (same approach as `trigger_device_update`).
  Both routes therefore **omit `response_model`** on the decorator,
  exactly like `trigger_device_update` (its decorator carries no
  `response_model`).
- **`device.node` cannot be empty** — `DeviceCreate.validate_node`
  rejects empty/whitespace node names at creation, so the broadcast
  target is always a non-empty string; no extra guard needed.

## 6. Configuration

No new settings. Existing env vars only:

| Variable | Role |
|---|---|
| `NODE_LISTENER` | Broadcast destination; empty ⇒ both endpoints 503 |
| `NODE_LISTENER_PORT` | Default `5053` |
| `SL_*` (optional) | AESSHA1 crypto — applied transparently by `iot_bootstrap` |

## 7. Out of scope

- An "all devices" broadcast variant (targets list = every node).
- Removing `ping_node_north.py` (the CLI keeps working; may be retired later).
- Node-side protocol changes — the `system.ping` / `system.{type}.get_hash`
  request events are assumed already implemented on the nodes.

## Implementation Checklist

- [x] 1. Inject standards (api/route-params, api/error-responses, api/response-format, api/auth, api/validation, testing/integration-fixtures) — *blocks 2–5*
- [x] 2. Add `ping` + `rescan` routes in `app/rest_server.py` (guards per §5, `tags=["device-queries"]`, hand-built dict responses) — *blocked by 1*
- [x] 3. Create `tests/integration/test_node_query_api.py` (monkeypatch `settings.node_listener` + `comm.send`; full-dict payload equality; ping 202/404/503, rescan 202/400/404/503) — *blocked by 2*
- [x] 4. Update `README.md` endpoint table (two rows) + `docs/api.md` (new `## Device Active Query` section after `## Device Events`) — *blocked by 2; parallel-safe with 3*
- [x] 5. Verify: `pytest tests/ -v` + `flake8 app/ tests/` clean; add Review section + Changelog entry below — *blocked by 3, 4*

## Review

**2026-11-13 — implementation complete, verified.**

- **Routes** — `ping_device` + `rescan_device` added in a new
  "Device active query endpoints" section of `app/rest_server.py`,
  placed after the device-update section. Guard order as pinned in §5:
  rescan validates `repo_type` first (400), then device (404), then
  listener (503); ping checks device (404) then listener (503).
  Responses are hand-built dicts with no `response_model` (per
  `api/response-format`), UDP payloads carry no `parameters` key.
- **Tests** — `tests/integration/test_node_query_api.py` with 8 tests
  (ping: 202/404/503; rescan: 202 parametrized over both
  `VALID_REPO_TYPES`, 400/404/503). Each 202 case asserts full-dict
  equality of the captured `comm.send` payload (absence of
  `parameters` is part of the assertion); error cases assert nothing
  was broadcast.
- **Docs** — two rows added to the README endpoint table; new
  `## Device Active Query` section in `docs/api.md` after
  `## Device Events`, matching its `### METHOD /path` style.
- **Verification** — `pytest tests/ -v`: 270 passed (8 new);
  `flake8 app/ tests/ --count --show-source --statistics`: clean.
- **Deviations from spec** — none; implementation follows §3–§5 as
  written.

## Changelog

### 2026-11-13
- Implementation complete: ping + rescan routes, integration tests, docs; full suite green (270 tests, flake8 clean)

### 2026-11-13
- Initial specification
