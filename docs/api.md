# API Reference

Base URL: `http://localhost:9092/api`

## Authentication

When `API_TOKEN` is configured, all endpoints require a Bearer token:

```
Authorization: Bearer <your-token>
```

When `API_TOKEN` is empty (default), authentication is skipped.

---

## Endpoints

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
  },
  {
    "id": 2,
    "chip_id": "DEF456",
    "node": "sensor-2",
    "created_at": "2026-06-07T12:05:00"
  }
]
```

**Errors**:

- `422` — Validation error (e.g., `limit > 1000`, `limit < 1`, `skip < 0`)

---

### GET /api/devices/{device_id}

Get a single device by ID.

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
  "created_at": "2026-06-07T12:00:00"
}
```

**Errors**:

- `404` — Device not found
- `422` — Validation error (e.g., `device_id < 1`)

---

### GET /health

Health check endpoint.

**Response** (200):

```json
{"status": "ok"}
```

---

## Data Model

### Device

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Auto-increment primary key |
| `chip_id` | string (255) | Device chip ID from IoT message |
| `node` | string (255) | Device name |
| `created_at` | datetime | Timestamp of first discovery |

**Unique constraint**: `(chip_id, node)` — no duplicate pairs.
