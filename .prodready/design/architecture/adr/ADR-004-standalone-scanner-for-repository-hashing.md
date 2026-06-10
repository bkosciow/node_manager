# ADR-004: Standalone Scanner for Repository Hashing

## Status
Accepted

## Date
2026-06-09

## Context

Repository management requires walking the `/upgrades` directory tree, computing SHA256 hashes for every file, and syncing the results to the database. This is a periodic operation — not a continuous service. The scanner needs access to the filesystem (`/upgrades` volume) and the same database as the main API service.

The question is: should the scanner run as a **standalone process** (separate entrypoint, separate container) or as a **scheduled worker inside the main service**?

## Decision

We will run the scanner as a **standalone Python script** (`repo_scanner.py`) in its own Docker container, triggered periodically. It connects to the same database using the same `DATABASE_URL` from config.

Key properties:
- **Independent lifecycle** — scanner runs on its own schedule, unaffected by API service restarts
- **Volume mounting** — `/upgrades` is mounted only in the scanner container, not the API container
- **Same DB, same config** — uses `app/config.py` (`pydantic_settings`) and `app/db/session.py` for database access
- **No FastAPI** — plain Python script with `if __name__ == "__main__"` entrypoint

## Consequences

### Positive
- **Clean separation of concerns** — API container serves HTTP; scanner container walks filesystem. Neither depends on the other
- **Volume isolation** — `/upgrades` volume is mounted only where needed (scanner), reducing API container attack surface
- **Independent scheduling** — scanner frequency is independent of API uptime. If API is down for deployment, scanner still runs
- **Burst isolation** — hash computation (SHA256 for every file) and bulk DB writes don't compete with API request handling for CPU or connection pool
- **Simple restart semantics** — API restart doesn't interrupt a scan in progress; scan restart doesn't affect API availability

### Negative
- **Two containers to manage** — slightly more Docker compose complexity (extra service definition)
- **Duplicate config** — scanner reads same `.env` variables. Risk of drift if one is updated and the other isn't. Mitigation: both read from the same `app/config.py` and same `.env` file
- **No real-time feedback** — scan progress is not visible via the API. Mitigation: scan is fast (tens of files); run duration is logged

### Risks
- **Concurrent scan + API write** — scanner writes `RepositoryFile` records while API reads them. Mitigation: same DB connection pool with proper transactions; reads are consistent within a transaction
- **Scanner crashes mid-run** — partial DB state. Mitigation: scanner uses per-repo transactions; crash recovery is a clean rescan on next run (idempotent — hashes are deterministic)

## Alternatives Considered

1. **Scheduled worker inside main service** (e.g., `APScheduler` trigger) — rejected because it couples filesystem access to the API process, shares the same container (volume must be mounted on API too), and competes for CPU/connection pool during scan bursts
2. **Cron job on the host** — rejected because it bypasses Docker, breaks containerization consistency, and requires host-level cron configuration
3. **Separate microservice with its own API** — rejected as overkill; the scanner is a fire-and-forget script, not a queryable service. Status is communicated via the main API's repo endpoints
