---
name: discover-standards-2026-10-30
description: Third /discover-standards run — 10 standards across messaging/, cli/, testing/; bootstrap helper mandated but not yet extracted
metadata:
  type: project
---

On 2026-10-30, ran /discover-standards on four areas: Messaging/UDP,
Standalone CLI scripts, Testing, and Global/cross-cutting. Created 13
standards:

- [[messaging-iot-bootstrap]] — UDP script preamble (logging → optional
  AESSHA1 cryptor from sl_* keys → Message.node_name/chip_id → comm.address);
  shared helper `app/services/iot_bootstrap.py` is the mandated pattern but
  NOT yet extracted — existing scripts keep the copy-paste block until
  touched; listener-only scripts may skip comm.address
- [[messaging-udp-topology]] — 5053/udp shared broadcast port (bound =
  expected, not a conflict), prod host-networking on purpose, comm.send send
  path, listener-only receive path (device_scaner.py is a listener, not a
  scanner despite its name)
- [[messaging-message-handler]] — handle() enqueues only; daemon worker +
  short-lived sessions; dedup cache + IntegrityError fallback; lazy imports;
  SUPPORTED_EVENTS is the sole extension point
- [[messaging-chip-id-normalization]] — int chip_ids → str(raw).strip(),
  empty/whitespace → skip + warn, non-dict data → no crash
- [[cli-standalone-db-bootstrap]] — scripts build their own engine from
  settings.database_url + create_all + local sessionmaker; never reuse
  app.db.session.SessionLocal
- [[cli-upgrades-dir-layout]] — ./upgrades/<repo>/{_microplate,_userspace}/
  layout, REPO_TYPE_MAP underscore-prefixed dirs, new type = dir + map entry
- [[cli-repo-sync-semantics]] — chunked SHA256, upsert +
  cleanup_repository_files mirrors disk, per-file OSError = continue
- [[testing-integration-fixtures]] — file-based SQLite (TestClient thread
  sharing), client/test_db fixtures, SAMPLE_DEVICE_* reuse, auth-off
- [[testing-unit-test-idiom]] — in-memory + check_same_thread, next(
  _session()) generator idiom, model import with noqa; in-memory breaks when
  SUT opens its own connection
- [[testing-message-handler-tests]] — MagicMock().data + queue asserts,
  lambda-replaced _process dispatch, file-based db_env for _process DB paths
- [[global-entity-triple]] — models+crud+schemas triple mandatory for every
  new entity, model registered in app/models/__init__ __all__, models/crud
  barrels exist while schemas/ is empty (barrel = target state, refactor
  when touched), naming: plural tablename, uq_ constraints, verb-first CRUD,
  Create/Response + from_attributes
- [[global-config-settings]] — settings singleton only, snake_case .env
  fields, empty-string-off is case-by-case (api_token/apprise_url/
  sl_passphrase, NOT a general contract), database_url required
- [[global-logging-apprise]] — module loggers + basicConfig locations,
  info/warning/exception discipline, Apprise available-but-unwired;
  ErrorHandler init normalized to the idiomatic form (the old
  `self=self` was legal Python, not a crash bug — verified 2026-10-30)

Also fixed a pre-existing YAML bug in index.yml: the api/route-params
description contained an unquoted ': ' and made the whole file unparseable
(previous runs never validated it).

**Why:** Runs 1–2 (2026-06-19, 2026-10-29) covered api/ and database/; the
2026-10-29 memory flagged Messaging/UDP, Testing, and Global/cross-cutting
as the remaining areas. This run closed all three, so all major areas
(api, database, messaging, cli, testing, global) now have standards.

**How to apply:** Inject `messaging/*` before new UDP scripts or message
handlers; `cli/*` before touching repo_scanner / upgrades layout;
`testing/*` when writing tests; `global/*` when adding a new entity or
settings field. Open items: extract `app/services/iot_bootstrap.py` when
the next UDP script is touched; add a `schemas/` barrel. (The
`ErrorHandler.__init__` line was normalized to the idiomatic form on
2026-10-30 and is guarded by tests/unit/test_apprise.py — the old
`self=self` looked like a bug but was valid Python.)
