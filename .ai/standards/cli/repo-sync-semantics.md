# Repo Sync Semantics (repo_scan service + repo_scanner CLI)

- SHA256 is chunked (8 KB read loop) — never slurp a whole file into
  memory.
- Per repo type: upsert a file record for every on-disk file
  (`upsert_repository_file`), tracking the `existing_filenames` set.
- Then `cleanup_repository_files(db, repo.id, existing_filenames)`
  deletes records for files no longer on disk — the DB file list must
  mirror the directory; a deleted file leaves no stale hash record.
- Per-file `OSError`/`PermissionError` → `logger.error` and continue —
  one unreadable file must not abort the whole scan. Unreadable files
  are left out of the cleanup set, so their rows are deleted in that
  run and re-added on the next successful scan.
- **No-wipe guard**: an empty file list is a no-op — `scan_repo` skips
  both upsert and `cleanup_repository_files`, so a missing or emptied
  on-disk directory must never wipe existing records.
- Scan core lives in `app/services/repo_scan.py` (shared by the API and
  the CLI) and is all `select()`-style. The legacy
  `db.query(Repository)` from the old `sync_repo_to_db` was removed in
  SPEC-004; a 4-arg legacy alias with the old signature remains in
  `repo_scanner.py` for import compatibility.
