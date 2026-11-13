# API Reference

Base URL: `http://localhost:9092/api`

## Authentication

When `API_TOKEN` is configured, all endpoints require a Bearer token:

```
Authorization: Bearer <your-token>
```

When `API_TOKEN` is empty (default), authentication is skipped.

---

## Health

### GET /health

Health check endpoint.

**Response** (200):

```json
{"status": "ok"}
```

---

## Devices

### GET /api/devices

List all discovered devices with pagination.

**Query Parameters**:

| Param | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `skip` | int | `0` | `>= 0` | Number of records to skip |
| `limit` | int | `100` | `1–1000` | Maximum records to return |

**Response** (200):

```json
[
  {
    "id": 1,
    "chip_id": "ABC123",
    "node": "sensor-1",
    "created_at": "2026-06-07T12:00:00"
  }
]
```

**Errors**:

- `422` — Validation error (e.g., `limit > 1000`, `limit < 1`, `skip < 0`)

---

### GET /api/devices/{device_id}

Get a single device by ID with logged events.

**Path Parameters**:

| Param | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `device_id` | int | `>= 1` | Device ID |

**Response** (200):

```json
{
  "id": 1,
  "chip_id": "ABC123",
  "node": "sensor-1",
  "created_at": "2026-06-07T12:00:00",
  "events": {
    "system.pong": {"version": "1.0.0"},
    "system.microplate.hash": {"sha256": "abc123"}
  }
}
```

**Errors**:

- `404` — Device not found
- `422` — Validation error (e.g., `device_id < 1`)

---

## Device Events

### GET /api/devices/{device_id}/events

Get all logged events for a device, keyed by event type.

**Response** (200):

```json
{
  "system.pong": {"version": "1.0.0"},
  "system.microplate.hash": {"sha256": "abc123"}
}
```

**Errors**:

- `404` — Device not found

---

### GET /api/devices/{device_id}/events/{event_type}

Get parameters for a specific event type.

**Path Parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `device_id` | int | Device ID |
| `event_type` | string | Event type (e.g., `system.pong`, `system.microplate.hash`, `system.userspace.hash`) |

**Response** (200):

```json
{"version": "1.0.0"}
```

**Errors**:

- `400` — Unsupported event type
- `404` — Device not found or event not found

---

## Device Active Query

Actively ask a device for fresh data. The node's replies (`system.pong`,
`system.microplate.hash`, `system.userspace.hash`) are ingested by the UDP
listener and persisted as `DeviceEvent` rows; both routes require `NODE_LISTENER`
to be configured and broadcast to `NODE_LISTENER:5053`.

### POST /api/devices/{device_id}/ping

Broadcast a `system.ping` message. The node replies with `system.pong`,
which the listener uses to refresh the device's `last_seen_at`.

**Path Parameters**:

| Param | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `device_id` | int | `>= 1` | Device ID |

**Response** (202):

```json
{
  "message": "Ping broadcast sent",
  "event": "system.ping",
  "target": "sensor-1"
}
```

**Errors**:

- `404` — Device not found
- `503` — Node listener not configured

---

### POST /api/devices/{device_id}/rescan/{repo_type}

Broadcast a `system.{repo_type}.get_hash` message so the device re-hashes
its local files and reports `system.{repo_type}.hash`. Works with or without
a repository of that type assigned to the device — the node simply reports
what it has.

**Path Parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `device_id` | int | Device ID |
| `repo_type` | string | `microplate` or `userspace` |

**Response** (202):

```json
{
  "message": "Rescan broadcast sent",
  "event": "system.userspace.get_hash",
  "target": "sensor-1"
}
```

**Errors**:

- `400` — Invalid repository type
- `404` — Device not found
- `503` — Node listener not configured

---

## Repositories

### GET /api/repos

List repositories by type with their files and SHA256 hashes.

**Query Parameters**:

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Repository type: `microplate` or `userspace` |

**Response** (200):

```json
[
  {
    "id": 1,
    "name": "node_north",
    "repo_type": "microplate",
    "created_at": "2026-06-07T12:00:00",
    "files": [
      {
        "id": 1,
        "filename": "core.py",
        "sha256": "a1b2c3d4e5f6...",
        "updated_at": "2026-06-09T08:00:00"
      }
    ]
  }
]
```

**Errors**:

- `400` — Invalid repo type

---

## Assignments

### POST /api/nodes/{device_id}/repos

Assign a repository to a node. If the node already has a repo of the same type, the old assignment is replaced.

**Path Parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `device_id` | int | Device (node) ID |

**Request Body**:

```json
{"repository_id": 1}
```

**Response** (200):

```json
{
  "id": 1,
  "device_id": 1,
  "repository_id": 1,
  "repo_type": "microplate",
  "assigned_at": "2026-06-09T10:00:00"
}
```

**Errors**:

- `404` — Device or repository not found
- `422` — Validation error

---

## Data Model

### Device

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Auto-increment primary key |
| `chip_id` | string (255) | Device chip ID from IoT message |
| `node` | string (255) | Device name |
| `created_at` | datetime | Timestamp of first discovery |

**Unique constraint**: `(chip_id, node)`

### DeviceEvent

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Auto-increment primary key |
| `device_id` | int | FK → devices.id |
| `event_type` | string (100) | Event identifier |
| `parameters` | JSON | Event-specific data |
| `logged_at` | datetime | Timestamp |

**Unique constraint**: `(device_id, event_type)`

### Repository

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Auto-increment primary key |
| `name` | string (255) | Repository name |
| `repo_type` | string (50) | `microplate` or `userspace` |
| `created_at` | datetime | Timestamp |

**Unique constraint**: `(name, repo_type)`

### RepositoryFile

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Auto-increment primary key |
| `repository_id` | int | FK → repositories.id |
| `filename` | string (255) | File name |
| `sha256` | string (64) | SHA256 hash |
| `updated_at` | datetime | Last updated |

**Unique constraint**: `(repository_id, filename)`

### NodeRepository

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Auto-increment primary key |
| `device_id` | int | FK → devices.id |
| `repository_id` | int | FK → repositories.id |
| `repo_type` | string (50) | `microplate` or `userspace` |
| `assigned_at` | datetime | Timestamp |

**Unique constraint**: `(device_id, repo_type)`
