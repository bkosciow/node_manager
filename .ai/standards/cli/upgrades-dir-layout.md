# Upgrades Directory Layout

- Directory source: `settings.upgrades_dir` (env `UPGRADES_DIR`, default
  `./upgrades`), read at call time in `app/services/repo_scan.py` — the
  shared scan core used by the API auto-scanner and the thin CLI
  `repo_scanner.py` (separate Docker container with a `/upgrades` volume
  mapping; the old `UPGRADES_DIR` module constant was removed in SPEC-002).
- Layout: `<upgrades_dir>/<repo_name>/{_microplate,_userspace}/<file>`.
- `REPO_TYPE_MAP` maps underscore-prefixed dir names to repo types:
  `{"_microplate": "microplate", "_userspace": "userspace"}`;
  unknown subdirectories are silently skipped.
- `_file_path` reverses the mapping: repo_type → `f"_{repo_type}"` dir.
- A new repo type needs: on-disk directory + `REPO_TYPE_MAP` entry. The
  hardcoded `("microplate", "userspace")` trap also applies to event
  types — see `database/event-hash-diff`.
