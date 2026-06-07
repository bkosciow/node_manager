# Data Model — Event Data Extension

## New Entities

### DeviceEvent
Stores the latest event payload for a device per event type.

- id: UUID (PK)
- device_id: Integer (FK → devices.id, CASCADE delete)
- event_type: String (one of: `system.pong`, `system.microplate.hash`, `system.userspace.hash`)
- parameters: JSON (the raw event parameters dict)
- updated_at: DateTime (auto-set on upsert)

## Relationships
- Device 1:N DeviceEvent (one device has up to 3 event records — one per event_type)

## Indexes & Constraints
- `(device_id, event_type)` — unique composite constraint (enforces one record per device per event type, enables upsert)
- `device_id` — foreign key with ON DELETE CASCADE

## Existing Entities (Unchanged)
- **Device**: no changes needed — `chip_id`, `node`, `created_at` as-is
