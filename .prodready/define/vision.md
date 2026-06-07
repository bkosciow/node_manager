# Vision

## Problem Statement
IoT devices send a flood of messages, and there's no service to reliably discover and deduplicate them before storing in a database. Without deduplication, the database gets hammered with redundant device entries.

## Target Users
Single operator (the developer). The API is consumed by a personal frontend application on an internal network.

## Core Value Proposition
Reliably discovering and deduplicating IoT devices from a high-volume message stream without drowning the database.

## Success Metrics
- Devices discovered with zero duplicates in the DB (enforced by unique constraint on `chip_id + node`)

## MVP Scope

### Must Have (MVP)
- **Message ingestion** — server listening for incoming IoT messages
- **Device discovery** — extract `chip_id` + `node`, save new pairs to DB
- **In-memory dedup cache** — check cache before touching DB (performance layer; DB unique constraint is the final guard)
- **REST API — list devices** — paginated endpoint for the frontend

### Nice to Have (Future)
- REST API — delete device
- Device status / last-seen tracking
- Persistent cache that survives restart
- Authentication on the API
