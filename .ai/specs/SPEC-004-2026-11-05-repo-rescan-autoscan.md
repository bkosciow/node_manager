# SPEC-002 — Repository Rescan & Auto-Scanner

## Overview

`Repository`/`RepositoryFile` records are written to the DB **only** when
`repo_scanner.py` runs — today that means a human (or CI) has to run
`make dev-repo-scanner` / the standalone container after every change to the
`/upgrades` volume. Until then, the hash diff (`get_repo_file_diff`,
`check_update_available`) and the upgrade flow in SPEC-001 act on **stale
data**: devices see `updates_available` for files that no longer exist, or
never see updates for files that just landed.

This spec adds two things:

1. **Force rescan endpoint** — `POST /api/repos/{repo_id}/rescan` (auth'd):
   re-hashes that repository's files on disk and syncs the records
   (upsert new/changed, remove records for files deleted from disk).
2. **Auto-scanner** — an in-app background loop in the api process that
   rescans **all** repositories every `REPO_SCAN_INTERVAL_MINUTES`
   (new `.env` setting, default **10**, `0` disables). No new dependencies
   (plain `threading` daemon thread; nothing in `requirements.txt` provides
   scheduling).

**What already exists (do not rebuild):**
- Scan core in the root CLI `repo_scanner.py`: `compute_sha256` (chunked
  SHA256), `discover_repos` (`{repo: {type: [filenames]}}` walk of
  `./upgrades/<repo>/_{_microplate,_userspace}` per the `upgrades-dir-layout`
  standard), `sync_repo_to_db` (upsert + cleanup mirrors disk, per-file
  `OSError` is logged and continued — the `repo-sync-semantics` standard).
- CRUD: `upsert_repository_file`, `cleanup_repository_files`
  (`app/crud/repository.py`).
- Config: `settings.upgrades_dir` (env `UPGRADES_DIR`, already wired into the
  api service in both docker-compose files).
- `Repository`/`RepositoryFile` models — no schema change in this spec.

**Reference patterns** (confirmed with the user):
- Extraction source: root `repo_scanner.py` CLI.
- Endpoint model: the POST action route `trigger_device_update`
  (`app/rest_server.py`) — validate parent, do the work, return a small
  result.

## User Stories

### Story 1 — Happy path: operator forces a rescan after a firmware drop

> **Persona**: Bartek, dropping a fixed `main.py` into
> `/upgrades/node_north/_userspace/` on the host. Wants the API and the
> devices' "updates available" flag to reflect it immediately, without
> restarting any scanner.

```
$ curl -X POST -H "Authorization: Bearer $TOKEN" \
    localhost:9092/api/repos/7/rescan
{
  "repo_name": "node_north",
  "repo_type": "userspace",
  "files_found": 3,
  "files_added": 1,
  "files_updated": 1,
  "files_unchanged": 1,
  "files_removed": 0,
  "errors": 0
}

$ curl -H "Authorization: Bearer $TOKEN" \
    "localhost:9092/api/repos?type=userspace"
[{"name": "node_north", ..., "files": [
    {"filename": "main.py", "sha256": "<new hash>", ...}, ...]}]
```

> **Behind the scenes**: the route resolves the repo row (404 if missing),
> enumerates the on-disk files via
> `list_repo_files_on_disk(repo.name, repo.repo_type)` (new helper in
> `app/services/repo_scan.py`: lists `{upgrades_dir}/{name}/_{type}/`,
> returns `[]` when the directory is absent), runs
> `scan_repo(db, repo.name, repo.repo_type, filenames)` — same
> upsert+cleanup semantics as the CLI — and returns the per-run counts.
> One request, one DB session, committed.

> **Change vs. current state**: Today there is no way to rescan over HTTP;
> the operator shells in and runs `repo_scanner.py` (which also rescans
> *every* repo). After this change: targeted, auth'd, API-visible, and the
> scan logic lives in the app package so the API and the CLI share it.

### Story 2 — Alternative: auto-scanner keeps a production DB fresh

> **Persona**: the on-call ops person — nobody runs scanners at 3 a.m. A
> release pipeline copies files to the mounted `/upgrades` volume; within
> the interval the records must be current so the upgrade diff is right.

```
# .env (api container)
REPO_SCAN_INTERVAL_MINUTES=10

# api container log, 10 minutes later
...
2026-11-05 03:10:00 INFO Scanned node_north (userspace): 3 file(s)
2026-11-05 03:10:00 INFO Auto-scan complete: 2 repo type(s), 0 error(s)
```

> **Behind the scenes**: on FastAPI startup (`app/rest_server.py`
> `startup()`), `start_auto_scan(settings.repo_scan_interval_minutes)`
> spawns a **daemon** thread: loop { open a fresh `SessionLocal()` session,
> `try/except/finally` — run `scan_all(db)`, log a one-line summary, close
> the session in `finally`; a failed iteration (e.g. transient DB outage)
> is logged and the loop continues on the next tick }, then
> `time.sleep(interval * 60)`. The thread dies with the process (daemon);
> no join/stop event needed for the current single-process uvicorn setup.
> `0` (or negative) disables the loop — logged at startup.

> **Change vs. current state**: Today the DB only changes when a human runs
> the CLI. After this change: records converge to disk state every
> `N` minutes with zero operator action, and the interval is a plain `.env`
> value (no new service, no cron container, no new dependency).

### Story 3 — Edge case: volume unmounted, records must survive

> **Persona**: Bartek after a misconfigured deploy — the `/upgrades`
> volume is missing from the api container, or a repo's type directory was
> removed. The DB must not be wiped.

```
$ curl -X POST -H "Authorization: Bearer $TOKEN" \
    localhost:9092/api/repos/7/rescan
{"detail": "No files found on disk for repository node_north (userspace)"}
# 404 — DB records untouched
```

> **Behind the scenes**: a scan with an **empty** file list would call
> `cleanup_repository_files(db, repo.id, set())` and delete *every*
> `RepositoryFile` row for that repo. So `scan_repo` treats "no files on
> disk" (missing dir, empty dir, or the whole upgrades dir absent) as a
> **no-op** — no upserts, **no cleanup**. The endpoint turns that into a
> 404. The auto-scanner applies the same rule per repo; while the upgrades
> dir is missing it logs one `logger.warning` **per tick** (per-tick, not
> once for the process lifetime) and idles, re-checking each tick —
> mounting the volume later heals it without a restart.
>
> **Change vs. current state**: Today the CLI never syncs a repo whose
> dir it didn't discover (so it is also safe), but there was no API
> surface to hit this path. The no-wipe rule is now explicit and shared by
> both entry points.

## Architecture

```
                        ┌─────────────────────────────────────────────┐
                        │ app/services/repo_scan.py   (NEW — shared) │
                        │  compute_sha256()                                 │
                        │  discover_repos(upgrades_dir=None)            │
                        │  list_repo_files_on_disk(name, type)          │
                        │  scan_repo(db, name, type, files) -> Report   │
                        │  scan_all(db) -> [Report]                      │
                        │  start_auto_scan(interval_minutes)  (thread)   │
                        └───────┬───────────────────┬──────────────────┘
                                │                   │
        ┌───────────────────────┴──┐        ┌───────┴───────────────┐
        │ repo_scanner.py (CLI)    │        │ app/rest_server.py     │
        │ main(): standalone        │        │ POST /api/repos/      │
        │ bootstrap (standard) →   │        │ {repo_id}/rescan →    │
        │ scan_all(db)             │        │  get_repository →     │
        │ (thin wrapper, keeps its │        │  disk list →          │
        │ own engine/SessionLocal) │        │  scan_repo → report   │
        └──────────────────────────┘        │ startup(): start_     │
                                             │  auto_scan(interval) │
                                             └──────────────────────┘

CRUD (unchanged): upsert_repository_file / cleanup_repository_files
Config:  settings.upgrades_dir (existing) + repo_scan_interval_minutes (new)
```

- **Extraction**: the scan core moves from the root `repo_scanner.py` into
  `app/services/repo_scan.py` as module-level functions, no base class
  (project coding standards: `logging.getLogger(__name__)` with %-style
  args, 100-char lines — note `app/services/comm.py` itself is a bare
  socket module with no logging). The `UPGRADES_DIR` module constant and
  the `__import__("app.schemas.repository", ...)` hack in
  `sync_repo_to_db` are removed — directory defaults to
  `settings.upgrades_dir` (config-settings standard: no magic defaults in
  code). `repo_scanner.py` keeps its **standalone DB bootstrap**
  (own `create_engine` + `create_all`, the `standalone-db-bootstrap`
  standard) and becomes a thin `main()` that calls `scan_all`. It
  re-exports `compute_sha256` and `discover_repos` from the service
  module, plus `sync_repo_to_db` as a legacy alias of `scan_repo`
  (returns `None`), so existing `from repo_scanner import ...` imports
  keep working. Because the `UPGRADES_DIR` constant goes away (the dir
  now defaults to `settings.upgrades_dir`), `tests/unit/test_repo_scanner.py`
  is updated to import from `app.services.repo_scan` and monkeypatch
  `settings.upgrades_dir` instead of `repo_scanner.UPGRADES_DIR`.
- **Report counting**: `scan_repo` returns a `RepoScanReport`
  (plain dataclass, not persisted):

  ```python
  @dataclass
  class RepoScanReport:
      repo_name: str
      repo_type: str
      files_found: int      # files enumerated on disk
      files_added: int      # new RepositoryFile rows
      files_updated: int    # existing row, hash changed
      files_unchanged: int  # existing row, hash identical
      files_removed: int    # rows deleted by cleanup
      errors: int           # per-file OSError count (scan continues)
  ```

  added/updated/unchanged is classified by comparing the existing
  `RepositoryFile.sha256` (fetched with a `select()` — query-style
  standard: new code uses `select()`) **before** calling the unchanged
  `upsert_repository_file` (the CRUD contract is not modified).
- **Unreadable-file semantics** (mirrors the CLI, confirmed with the
  user): a file that exists on disk but fails to hash (permission
  error, vanished mid-scan) is counted in `errors` (the scan continues,
  per `repo-sync-semantics`) and its `RepositoryFile` row **is deleted
  in that run** — the cleanup set is built only from successfully
  hashed filenames, exactly like today's `sync_repo_to_db` — then
  re-added on the next successful scan. Rationale: a file we cannot
  read here also cannot be served to nodes (`serve_upgrade_file` would
  404), so keeping its row would lie in the hash diff.
- **No-wipe guard** (Story 3): `scan_repo` with an empty file list skips
  both upsert and `cleanup_repository_files` and reports `files_found=0`.
  Callers surface it: endpoint → 404; auto-scan → skipped repo, logged.
- **Auto-scanner thread** (Story 2): started from the existing
  `@app.on_event("startup")` handler in `app/rest_server.py` (no new
  startup plumbing). Details:
  - `threading.Thread(target=_auto_scan_loop, args=(interval,), daemon=True)`
  - one **fresh** `SessionLocal()` per iteration (the app's
    `SessionLocal` from `app/db/session.py`; never a request session;
    closed in `finally` — session-commit / standalone-session
    discipline),
  - per-iteration `try/except Exception: logger.exception(...)` so a DB
    blip can't kill the loop;
  - `interval_minutes <= 0` → no thread, one `logger.info` at startup
    ("auto-scanner disabled" — this is also the pytest guard, see
    Tests);
  - upgrades dir missing at a tick → `discover_repos` returns `{}`, the
    tick logs one `logger.warning` and the loop idles until the next
    tick, which re-checks (heals on remount; one warning per tick while
    still missing, not once for the process lifetime).
  - Under uvicorn `--reload` (dev) and container restarts the thread is
    recreated on each process start — no state on disk.
  - **Tests**: `tests/conftest.py`'s `client` fixture uses
    `with TestClient(app)`, so Starlette's lifespan **does run**
    `startup()` on every test; a spawned loop would hit the app's
    `SessionLocal` (the real `settings.database_url`), not the test
    SQLite. Guard (confirmed): `tests/conftest.py` sets
    `settings.repo_scan_interval_minutes = 0` at module level, so the
    `interval <= 0` no-op path prevents any thread from ever spawning
    under pytest. Unit tests invoke the loop function directly with a
    monkeypatched `time.sleep`; integration tests never start the loop.

## Data Models

No new or changed tables. `repositories` and `repository_files`
(`app/models/repository.py`) are reused as-is, including
`uq_repo_file(repository_id, filename)` and the
`files` cascade-delete-orphan relationship. `RepoScanReport` is an
in-memory dataclass only.

## API Contracts

### `POST /api/repos/{repo_id}/rescan` — force rescan (auth'd)

Auth: `token: str = Depends(verify_token)` (never bypassed).
Route tags: `tags=["repos"]`. Parameter order per the route-params
standard: path (`repo_id: int = Path(ge=1)`) → `db` → `token`.
On-disk enumeration for the single repo: `list_repo_files_on_disk(
repo.name, repo.repo_type)` — direct listing of
`{upgrades_dir}/{name}/_{type}/`, `[]` when the dir is absent (feeds
the 404 no-wipe path). The auto-scanner's all-repo walk keeps using
`discover_repos()`.

| Outcome | Status | Body |
|---|---|---|
| Repo row missing | 404 | `{"detail": "Repository not found"}` |
| Type dir missing on disk / zero files | 404 | `{"detail": "No files found on disk for repository {name} ({type})"}` |
| Success | 200 | `RepoRescanResponse` (below) |

Synchronous 200 (the scan is local and fast; `202` is reserved for the
UDP-broadcast action in `trigger_device_update`).

`RepoRescanResponse` (new, in `app/schemas/repository.py`). The route
declares `response_model=RepoRescanResponse` (coding standard: every
endpoint gets a response_model); the payload is a hand-built dict, so
the model needs no `from_attributes` / ORM integration:

```python
class RepoRescanResponse(BaseModel):
    repo_name: str
    repo_type: str
    files_found: int
    files_added: int
    files_updated: int
    files_unchanged: int
    files_removed: int
    errors: int
```

The response mirrors the `RepoScanReport` fields (plus 404s via
`HTTPException` detail strings, per the error-responses standard).

## Configuration

| Variable | Field (`app/config.py`) | Default | Meaning |
|---|---|---|---|
| `REPO_SCAN_INTERVAL_MINUTES` | `repo_scan_interval_minutes: int = 10` | `10` | Auto-scan period in minutes; `0` (or negative) disables the auto-scanner |

- Read only via the `settings` singleton (config-settings standard).
- Wire into both compose files' **api** service env blocks (after
  `UPGRADES_DIR`, both files): `REPO_SCAN_INTERVAL_MINUTES=${REPO_SCAN_INTERVAL_MINUTES:-10}`.
- Document in `.env.example`.
- The CLI is unaffected by the new variable (it stays one-shot).
- Under pytest, `tests/conftest.py` forces `repo_scan_interval_minutes = 0`
  so the auto-scanner never runs during tests (see Architecture →
  Auto-scanner thread → Tests).

## Implementation Checklist

Dependencies: each task lists what blocks it (`<-`).

- [x] 1. `/inject-standards` — api/error-responses, api/route-params, cli/repo-sync-semantics, global/config-settings, database/query-style, testing/integration-fixtures, testing/unit-test-idiom
- [x] 2. `app/services/repo_scan.py` — scan core: `RepoScanReport` dataclass, `compute_sha256`, `discover_repos`, `list_repo_files_on_disk`, `scan_repo` (added/updated/unchanged classification, no-wipe guard, OSError semantics) `<- 1`
- [x] 3. `app/services/repo_scan.py` — auto-scanner: `start_auto_scan` + `_auto_scan_loop` (daemon thread, fresh `SessionLocal` per tick, per-tick try/except, `<= 0` no-op) `<- 2`
- [x] 4. `app/config.py` — `repo_scan_interval_minutes: int = 10` `<- 1`
- [x] 5. `app/schemas/repository.py` — `RepoRescanResponse` `<- 1`
- [x] 6. `repo_scanner.py` — thin CLI wrapper: standalone bootstrap, `main()` → `scan_all`, re-exports (`compute_sha256`, `discover_repos`, `sync_repo_to_db` legacy alias) `<- 2`
- [x] 7. `app/rest_server.py` — `POST /api/repos/{repo_id}/rescan` route (`response_model=RepoRescanResponse`, no-wipe 404) + `startup()` calls `start_auto_scan(settings.repo_scan_interval_minutes)` `<- 2, 3, 4, 5`
- [x] 8. `tests/conftest.py` — module-level `settings.repo_scan_interval_minutes = 0` (auto-scan guard under pytest) `<- 4`
- [x] 9. `tests/unit/test_repo_scan.py` (new) — report counts, no-wipe, `list_repo_files_on_disk`, auto-scan loop with monkeypatched `time.sleep`, `<= 0` no-op `<- 2, 3`
- [x] 10. `tests/unit/test_repo_scanner.py` — migrate imports to `app.services.repo_scan`, monkeypatch `settings.upgrades_dir` instead of `repo_scanner.UPGRADES_DIR` `<- 2`
- [x] 11. `tests/integration/test_repo_api.py` — `TestRepoRescan`: happy-path counts, 404 missing repo, 404 no-files-on-disk `<- 7, 8`
- [x] 12. `docker-compose.yml`, `docker-compose.prod.yml`, `.env.example` — `REPO_SCAN_INTERVAL_MINUTES` wiring (api service env blocks + documented default) `<- 4`

After all tasks: `/verify-standards` → build (`pytest tests/ -v` + flake8) → spec changelog sync.

## Changelog

### 2026-11-05
- Implemented (all 11 remaining tasks). Two pinned-down details:
  - `sync_repo_to_db` legacy alias keeps the old 4-arg signature
    `(db, repo_name, repo_type, filenames) -> None` and delegates to
    `scan_repo` (report discarded) — import compatibility, exact return
    contract of the removed CLI function.
  - "Found existing repository" is logged at DEBUG (not INFO) so the
    auto-scanner's per-tick output stays clean; "Created repository"
    stays INFO.
- Full suite green: 249 passed, flake8 clean.
- `/verify-standards` (user run): updated the stale
  `cli/upgrades-dir-layout` standard (directory now comes from
  `settings.upgrades_dir`); per user decision, new test queries in
  `test_repo_scan.py` / `test_repo_api.py` converted to `select()`
  style — strict reading of GUARDRAILS BLOCK #2 (pre-existing legacy
  test queries in `test_repo_scanner.py` left untouched). 249 passed.

### 2026-11-05
- Spec review fixes: corrected the pytest claim (TestClient's lifespan
  does run `startup()` — `tests/conftest.py` now forces
  `repo_scan_interval_minutes = 0`, so no auto-scan thread ever spawns
  under pytest); pinned unreadable-file semantics (row deleted, mirrors
  the CLI, re-added on the next successful scan); per-tick
  `logger.warning` while the upgrades dir is missing; added the
  `list_repo_files_on_disk` helper to the service module and API
  contract; unified the "0 disables" wording; pinned
  `response_model=RepoRescanResponse` on the route and the CLI
  re-export set (`sync_repo_to_db` legacy alias) with the
  `test_repo_scanner.py` import/monkeypatch migration.

### 2026-11-05
- Initial specification: forced rescan endpoint (`POST /api/repos/{id}/rescan`)
  and interval-based in-app auto-scanner (`REPO_SCAN_INTERVAL_MINUTES`,
  default 10, `0` disables); shared scan core in `app/services/repo_scan.py`;
  no-wipe guard for empty/missing on-disk dirs; no new dependencies.
