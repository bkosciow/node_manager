# Logging & Notifications

- Module logger: `logger = logging.getLogger(__name__)` in every app
  module.
- `logging.basicConfig(level=logging.INFO)` is called at module top in
  `app/rest_server.py` and in the standalone scripts (device_scaner.py,
  dump_messages.py, ping_node_north.py, repo_scanner.py) — the app and
  scripts configure the root logger themselves.
- Level discipline: `logger.info` for state changes (device created,
  event upserted); `logger.warning` for skipped/malformed input;
  `logger.exception` for unexpected failures inside the discovery worker.
- `app/services/apprise.py` is available but **NOT wired** — `Apprise` /
  `ErrorHandler` are referenced nowhere in the repo. Don't assume
  notifications are live.
- `ErrorHandler.__init__` historically used the unconventional (but legal)
  form `logging.Handler.__init__(self=self)` — `self=` binds the instance
  by keyword to the parameter named `self`, so it worked despite looking
  like a bug. Normalized to the idiomatic `logging.Handler.__init__(self)`
  on 2026-10-30; guarded by `tests/unit/test_apprise.py`.
- Apprise payload contract (when wired): POST JSON
  `{"body", "title", "tag": settings.apprise_tag}` to
  `settings.apprise_url`; silent no-op when the URL is empty.
