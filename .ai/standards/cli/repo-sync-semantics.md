# Repo Sync Semantics (repo_scanner.py)

- SHA256 is chunked (8 KB read loop) — never slurp a whole file into
  memory.
- Per repo type: upsert a file record for every on-disk file
  (`upsert_repository_file`), tracking the `existing_filenames` set.
- Then `cleanup_repository_files(db, repo.id, existing_filenames)`
  deletes records for files no longer on disk — the DB file list must
  mirror the directory; a deleted file leaves no stale hash record.
- Per-file `OSError`/`PermissionError` → `logger.error` and continue —
  one unreadable file must not abort the whole scan.
- `sync_repo_to_db` uses legacy `db.query(Repository)` — refactoring
  debt; use `select()` when touching it (GUARDRAILS BLOCK #2).
