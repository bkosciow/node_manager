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
- Change detection in repo files (notify when files differ from stored hashes)

## Feature: Repository Management

### Problem Statement
Each IoT device (node) runs two kinds of software: a framework (microplate) and user code (userspace). There's no way to track which version of each file is deployed, or to assign a local software repository to a node.

### Target Users
Single operator (the developer). The API is consumed by a personal frontend application on an internal network. Hash calculation runs periodically as a Docker container.

### Core Value Proposition
Keeping file hashes up-to-date — every file in the `/upgrades` directory has a current SHA256 hash in the database after each scan run.

### Success Metrics
- Every file in `/upgrades` has a current hash in the DB after each scan run.

### Must Have (MVP)
- **Hash scanning script** — standalone Python script that walks `/upgrades`, calculates SHA256 for each file, stores/updates in DB
- **Repository data model** — repo name, repo type (`_microplate` / `_userspace`), filename, SHA256 hash
- **API — list repos by type** — return repos with their files and hashes
- **API — assign repo to node** — assign one microplate repo and/or one userspace repo per node
- **Periodic execution** — scan script runs in its own Docker container with `/upgrades` volume mapping

### Nice to Have (Future)
- Change detection — notify when on-disk files differ from stored hashes
