# Upgrades Directory Layout

- `UPGRADES_DIR = "./upgrades"` — repo_scanner.py runs as a separate Docker
  container with a `/upgrades` volume mapping (see its docstring).
- Layout: `./upgrades/<repo_name>/{_microplate,_userspace}/<file>`.
- `REPO_TYPE_MAP` maps underscore-prefixed dir names to repo types:
  `{"_microplate": "microplate", "_userspace": "userspace"}`;
  unknown subdirectories are silently skipped.
- `_get_file_path` reverses the mapping: repo_type → `f"_{repo_type}"` dir.
- A new repo type needs: on-disk directory + `REPO_TYPE_MAP` entry. The
  hardcoded `("microplate", "userspace")` trap also applies to event
  types — see `database/event-hash-diff`.
