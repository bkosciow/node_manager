# ADR-005: Full Rescan Hash Strategy

## Status
Accepted

## Date
2026-06-09

## Context

The scanner walks `/upgrades/{repo_name}/{_microplate|_userspace}/` and computes SHA256 for every file. The constitution states: "Hash must match actual file on disk — stored SHA256 is the source of truth; if it doesn't match the file, the scan is wrong."

The question is: should the scanner do a **full rescan** (recalculate every hash on every run, compare with DB, sync) or an **incremental scan** (only hash files whose modification time changed since the last scan)?

## Decision

We will use a **full rescan** strategy on every run:

1. Walk `/upgrades` and compute SHA256 for every file
2. For each repo+type+filename, upsert into `RepositoryFile` (insert if new, update hash if changed)
3. Delete `RepositoryFile` records that no longer have a corresponding file on disk

This is idempotent: running the scanner N times produces the same DB state as running it once.

## Consequences

### Positive
- **Correctness guarantee** — stored hash always matches on-disk file. No reliance on modification times, which can be faked, restored from backup, or changed by the filesystem
- **Detects deletions** — full snapshot makes it trivial to find files that disappeared (DB record exists, file doesn't → delete record)
- **Idempotent** — scanner can be run at any time, any number of times, with the same result. No state carried between runs
- **Simple** — no "last scan timestamp" to store, no modification time comparison logic, no edge cases around touched-but-unchanged files
- **Fast enough** — MVP scale is ~10 repos with flat file structures (no subdirs). SHA256 of a few dozen files takes milliseconds

### Negative
- **Redundant work** — re-hashes unchanged files on every run. At MVP scale this is negligible
- **No "what changed" delta** — scanner updates hashes but doesn't report which files changed. Mitigation: "change detection" is listed as a future feature (Nice to Have)

### Risks
- **File count grows to thousands** — full rescan becomes measurable work. Mitigation: monitor scan duration, switch to incremental (mtime-based) scan if duration exceeds threshold
- **File modified mid-scan** — hash captured at point-in-time. Acceptable — scanner is not a real-time monitor, it's a periodic snapshot

## Alternatives Considered

1. **Incremental scan (mtime-based)** — only hash files newer than last scan timestamp. Rejected because: (a) mtime can be unreliable (restores, manual touches, NFS), (b) cannot detect deletions without full walk anyway, (c) adds state to manage (last scan timestamp per repo), (d) no benefit at MVP scale
2. **Content-addressed store** — use hash as the key, skip if hash already exists in DB. Rejected because filename matters (which file has which hash), not just the hash itself. Two files can share the same content but serve different purposes.
3. **Filesystem watch (inotify/fswatch)** — react to file changes in real-time. Rejected because: (a) adds complexity (watcher process, event coalescing), (b) misses changes made outside the watcher's scope (manual edits, volume remounts), (c) overkill for periodic scan use case
