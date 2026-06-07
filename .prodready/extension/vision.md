# Vision — Event Data Collection Extension

## Problem Statement
IoT devices broadcast special events (`system.pong`, `system.microplate.hash`, `system.userspace.hash`) carrying runtime diagnostics and file hashes. Currently, these messages are ignored — the service only extracts `(chip_id, node)` for device discovery. The operator has no visibility into device health, firmware version, or file integrity.

## Target Users
Single operator (solo developer). The API is consumed by a personal frontend application on an internal network.

## Core Value Proposition
Capture and store the latest event payload per device per event type so the operator can monitor device health and file integrity at a glance.

## Success Metrics
- Every incoming event of the 3 supported types is stored (upserted) with zero data loss.
- Latest value is always retrievable per device per event type via the API.

## Scope

### Must Have (This Extension)
- **Event routing** — detect `system.pong`, `system.microplate.hash`, `system.userspace.hash` in incoming messages
- **Event data storage** — upsert JSON parameters linked to the source device (create device first if unknown)
- **REST API — get event data** — retrieve latest event payload per device per event type

### Nice to Have (Future)
- Historical timeline of event values (append-only mode)
- Alerting on hash changes (notify via Apprise when hash differs from last value)
- WebSocket push for real-time updates
