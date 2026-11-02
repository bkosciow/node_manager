---
name: discover-standards-2026-10-29
description: Second /discover-standards run — 4 Database/CRUD standards created; GUARDRAILS BLOCK rules + architectural decisions filled
metadata:
  type: project
---

On 2026-10-29, ran /discover-standards focused on Database/CRUD. Created 4 standards:

- [[database-session-commit]] — db: Session first arg, CRUD owns commit (flexible route-level exception), refresh after write
- [[database-none-integrity-contract]] — None → 404, string-matched IntegrityError → 409, get-or-create rollback fallback (discovery-specific)
- [[database-query-style]] — select() mandatory for new code, legacy db.query() is refactoring debt, uq_ constraint naming, FK cascade is per-model choice
- [[database-event-hash-diff]] — protocol-defined system.{repo_type}.hash events, JSON parameter storage, diff semantics, hardcoded ("microplate", "userspace") trap

GUARDRAILS.md filled from this run (user-approved as-is): 3 BLOCK rules (never rename protocol event types; select() for new query code; no HTTP semantics in CRUD) + 2 architectural decisions (schema = models, no migration tool; mixed query styles).

**Why:** First run (2026-06-19) left Database/CRUD undocumented; it's the layer most likely to be violated when agents add entities or endpoints.

**How to apply:** Inject `database/*` standards before touching `app/models/`, `app/crud/`, or `app/db/`. Remaining areas not yet documented: Messaging/UDP, Testing, Global/cross-cutting.
