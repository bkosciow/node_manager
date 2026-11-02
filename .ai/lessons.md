# Lessons

General rules learned from corrections/reviews, to save time in future
tasks. Newest last.

## 2026-11-02 — Union-diff device-only entries deadlock node upgrades

`get_repo_file_diff` returns the sorted UNION of repo and device hash
dicts, where `device_hash`/`repo_hash` are `None` on the side that lacks
the file. Device-only entries (`repo_hash is None`) are files that exist
on the node but not in the repo — there is nothing for the node to
download. If such entries are passed to a node as "files to fetch", the
node 404s, aborts the whole upgrade, and the diff is still non-empty,
so every re-trigger re-broadcasts the same unfetchable list — a
permanent upgrade deadlock.

**Rule:** any consumer of `get_repo_file_diff` that acts on the diff
(broadcast, download list, session `files`) must filter to
`[f for f in diff if f["repo_hash"] is not None]` — repo-side entries
only. "Nothing updatable" = the filtered list is empty, 404 the
request. Covered by `TestTriggerDeviceUpdate.test_device_only_diff_returns_404`.

## 2026-11-02 — "Update pending" flags must iterate the target side only

A flag meaning "device needs an action to reach repo state" must be
computed by iterating the **repo (target) files only**:
`any(device.get(f) != h for f, h in repo.items())`. Symmetric dict
equality (`device_hashes != repo_hashes`) implicitly counts
device-only files and sets the flag permanently — the action can never
satisfy it (an upgrade pushes repo state; it cannot remove
device-local files). Device-only entries belong in informational
views (device detail diff), never in the trigger/flag logic.
Same shape as the union-diff lesson above: the diff may be a union,
but every *consumer that acts* must be repo-side.

## 2026-11-02 — Required body param after defaulted params is a SyntaxError

FastAPI routes mix defaulted params (`Path()`, `Depends()`) with a
Pydantic body. A bare `body: SomeModel` (no default) placed after
defaulted params is a Python `SyntaxError: parameter without a default
follows parameter with a default`. The codebase convention is
`body: SomeModel = ...` (Ellipsis — still a required body in FastAPI),
which makes any position legal. Place body directly after path/query
params (see `api/route-params` standard).
