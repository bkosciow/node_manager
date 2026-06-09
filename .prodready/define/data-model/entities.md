# Data Model

## Entities

### Device
- id: int (auto-increment primary key)
- chip_id: str (unique device identifier from message)
- node: str (device name, not unique)
- created_at: datetime (timestamp of first discovery)

### Repository
- id: int (auto-increment primary key)
- name: str (repo name, e.g. "node_north")
- repo_type: str ("microplate" or "userspace")
- created_at: datetime (timestamp of first scan)

### RepositoryFile
- id: int (auto-increment primary key)
- repository_id: int (FK → Repository)
- filename: str (file name, one level, no subdirs)
- sha256: str (SHA256 hash of file contents)
- updated_at: datetime (timestamp of last hash calculation)

### NodeRepository
- id: int (auto-increment primary key)
- device_id: int (FK → Device)
- repository_id: int (FK → Repository)
- repo_type: str ("microplate" or "userspace")
- assigned_at: datetime (timestamp of assignment)

## Relationships
- Repository 1:N RepositoryFile (cascade delete)
- Device 1:0..2 NodeRepository (a node can have 0, 1, or 2 assignments — one per type)
- Repository 1:N NodeRepository (same repo can be assigned to multiple nodes)

## Indexes
- (chip_id, node) — unique composite (enforces no duplicates)
- (name, repo_type) — unique composite on Repository (one repo name per type)
- (repository_id, filename) — unique composite on RepositoryFile (one hash per file)
- (device_id, repo_type) — unique composite on NodeRepository (one repo per type per node)
- id — primary key (auto-indexed on all tables)
