# User Stories — Event Data Extension

## Epic 1: Event Data Collection

### US-007: Route Special Events in Message Handler
**As a** device discovery service
**I want to** detect special event types (`system.pong`, `system.microplate.hash`, `system.userspace.hash`) in incoming messages
**So that** event payloads can be captured and stored

**Acceptance Criteria**:
- [ ] Given a message with `message['event']` equal to `system.pong`, when the handler processes it, then the event is routed for storage
- [ ] Given a message with `message['event']` equal to `system.microplate.hash`, when the handler processes it, then the event is routed for storage
- [ ] Given a message with `message['event']` equal to `system.userspace.hash`, when the handler processes it, then the event is routed for storage
- [ ] Given a message with an unrecognized or missing `event` field, when the handler processes it, then device discovery proceeds as normal (no event storage)

**Priority**: P0
**Estimate**: S

---

### US-008: Store Event Data (Upsert)
**As a** device discovery service
**I want to** store the latest event parameters per device per event type
**So that** the operator always sees the current state

**Acceptance Criteria**:
- [ ] Given a `system.pong` event for an existing device, when the handler stores it, then the existing `DeviceEvent` record is updated with new parameters
- [ ] Given a `system.microplate.hash` event for an existing device, when the handler stores it, then a new or updated `DeviceEvent` record is created with event_type `system.microplate.hash`
- [ ] Given a `system.userspace.hash` event for an existing device, when the handler stores it, then a new or updated `DeviceEvent` record is created with event_type `system.userspace.hash`
- [ ] Given an event for a device that does NOT exist in the DB, when the handler processes it, then the device is created first (from `chip_id` + `node`), then the event is stored
- [ ] Given an event with `parameters` as a dict, when stored, then the parameters are serialized as JSON in the database

**Priority**: P0
**Estimate**: M

---

### US-009: Ensure Device Exists Before Event Storage
**As a** device discovery service
**I want to** automatically create a device record when an event arrives for an unknown `(chip_id, node)` pair
**So that** event data is never orphaned

**Acceptance Criteria**:
- [ ] Given an event arrives with `chip_id` and `node` that do not match any existing device, when processing completes, then a new Device record is created
- [ ] Given an event arrives with `chip_id` and `node` that match an existing device, when processing completes, then no new Device record is created
- [ ] Given device creation fails (integrity error), when processing completes, then the event storage is skipped gracefully (no crash)

**Priority**: P0
**Estimate**: S

---

## Epic 2: Event Data API

### US-010: Get Latest Event Data for a Device
**As a** frontend operator
**I want to** fetch the latest event data for a specific device and event type
**So that** I can view device health or file hashes

**Acceptance Criteria**:
- [ ] Given a device has a stored `system.pong` event, when I GET `/api/devices/{device_id}/events/system.pong`, then I receive the parameters as JSON
- [ ] Given a device has no stored event for the requested type, when I GET `/api/devices/{device_id}/events/{event_type}`, then a 404 is returned
- [ ] Given an invalid `device_id`, when I GET `/api/devices/{device_id}/events/{event_type}`, then a 404 is returned
- [ ] Given an unsupported `event_type`, when I GET `/api/devices/{device_id}/events/{event_type}`, then a 400 is returned

**Priority**: P0
**Estimate**: S

---

### US-011: Get All Event Data for a Device
**As a** frontend operator
**I want to** fetch all stored event types for a device in one call
**So that** I can see a complete snapshot of device state

**Acceptance Criteria**:
- [ ] Given a device has multiple event types stored, when I GET `/api/devices/{device_id}/events`, then I receive a JSON object keyed by event_type with parameters as values
- [ ] Given a device has no stored events, when I GET `/api/devices/{device_id}/events`, then I receive an empty object `{}`
- [ ] Given an invalid `device_id`, when I GET `/api/devices/{device_id}/events`, then a 404 is returned

**Priority**: P1
**Estimate**: S

---

## Epic 3: Integration

### US-012: Event Processing in Background Worker
**As a** system operator
**I want to** event data stored in the background worker thread (not blocking message ingestion)
**So that** the service handles high message volume without dropping events

**Acceptance Criteria**:
- [ ] Given events are queued in the handler, when the worker processes them, then they are upserted to the database
- [ ] Given the worker encounters a DB error during upsert, when processing completes, then the error is logged and the worker continues

**Priority**: P0
**Estimate**: S
