# GUARDRAILS

> Inviolable project rules. Every developer and AI agent MUST follow these.
>
> This file does NOT describe project structure (see `AGENTS.md`)
> or code patterns (see `.ai/standards/`).
> This file defines **boundaries that must never be crossed**.
>
> The sections below start with a small set of rules that apply to most web
> projects. Extend them with project-specific rules after running
> `/discover-standards` and talking with the team about past incidents,
> compliance requirements, and architectural non-negotiables.

## Absolute prohibitions

### STOP — immediate revert

Violation = revert NOW, no discussion.

1. **NEVER** store PII (email, IP, phone, full name, payment data) as plaintext in the database — use a hash (for lookup) + encrypted ciphertext (for retrieval), or column-level encryption provided by your DB/ORM.
2. **NEVER** build SQL queries via string concatenation or template literal interpolation of user input — always use parameterized queries (`$1`, `?`, `:name`, etc.) of your DB driver / ORM.
3. **NEVER** commit secrets (JWT signing keys, encryption keys, API keys, DB passwords, OAuth client secrets) to the repository — environment variables only, via `.env` / your secrets manager.
4. **NEVER** log PII in plaintext — strip query strings from logged URLs; hash or mask emails, IPs, tokens before they hit any log sink.

<!--
Add your own STOP-level rules below. Guidance: only add a rule here if
violating it causes a security, legal, or data-integrity incident —
everything softer belongs in BLOCK.
Examples:
5. NEVER bypass row-level security policies in admin tooling
6. NEVER write across tenant boundaries in a multi-tenant query
-->

### BLOCK — do not merge without fix

Violation = fix before merge, PR blocked.

1. **NEVER** rename or modify protocol-defined event types (the
   `system.{repo_type}.hash` family, e.g. `system.microplate.hash`) — devices
   send these strings verbatim; renaming orphans every stored hash event.
2. **NEVER** add new legacy-style `db.query(Model)` query code — new
   CRUD/query code must use SQLAlchemy 2.0 `select()` style. Legacy functions
   get refactored when touched, not extended.
3. **NEVER** put HTTP semantics in the CRUD layer — no status codes, no
   HTTPException; CRUD returns `None` for missing rows/parents and lets
   constraint violations propagate. Routes translate (404 / 409).

## Decision priorities

When values conflict, this hierarchy resolves:

1. **PII and user-data security** — breaches have legal, reputational, and often existential consequences.
2. **Data integrity** — corrupted data with no rollback is worse than downtime.
3. **Public / customer-facing surface stability** — public endpoints, embedded widgets, and integrations that third parties depend on.
4. **API contract compatibility** — breaking changes cascade to every client.
5. **Code readability and consistency** — predictable patterns make multi-developer + AI development sustainable.

<!--
Adjust this ordering if your project has a different top priority (e.g. a
realtime system might place availability above data integrity). Keep it to
5 items max — a priority list that long stops being a priority list.
-->

## Architectural boundaries

<!--
Fill in the layer boundaries that must not be crossed in your codebase.
Format: {Layer A} -> NEVER {action that violates layering} ({why})
Examples:
1. Route handler -> NEVER writes raw SQL — always through the Repository layer
2. Repository -> NEVER imports from routes/ or middlewares/ — data layer doesn't know about transport
3. UI components -> NEVER call the database directly — always via the API client
4. Background worker -> NEVER imports HTTP framework code
-->

_(add project-specific boundaries here)_

## Consistency rules

<!--
"When you add X, you must also add Y." These keep the codebase symmetric.
Examples:
1. When adding a new PII field -> ALWAYS add the _hash + _encoded pair
2. When adding a new endpoint under /api/private/ -> ALWAYS add the auth middleware
3. When adding a user-facing string -> ALWAYS add a translation key (no hardcoded text)
4. When adding a new DB model -> ALWAYS create an interface, a Repository, and an export
-->

_(add project-specific consistency rules here)_

## Allowed exceptions

<!--
Document the edge cases where the rules above can be intentionally broken,
and WHY. Without this section, juniors and AI agents will either bend rules
silently or refuse to ship valid changes.
Examples:
1. console.* in browser-only widget code — the server logger isn't available there
2. Raw interpolation of a hardcoded constant column name — parameterization
   can't cover identifiers in all drivers
-->

_(add project-specific allowed exceptions here)_

## Definition of "done"

A change is complete ONLY when:

- [ ] The project's linter / formatter passes with no errors (see `Commands` in AGENTS.md)
- [ ] The type-checker / compiler passes with no errors
- [ ] Tests relevant to the change pass locally
- [ ] No secrets or plaintext PII in staged files (see Prohibitions #3, #4)
- [ ] Every new rule that was introduced during implementation has been captured via `/sync-standards` or an entry in this file
- [ ] The spec file (if any) has its `## Implementation Checklist` updated

<!--
Add project-specific "done" criteria here — e.g. "widget rebuild has run",
"migration has been tested against a prod-sized snapshot", "translations
have been exported".
-->

## Architectural decisions

### Schema = models, no migration tool
- **Choice**: schema is defined entirely by the SQLAlchemy models in
  `app/models/`; `init_db()` runs `Base.metadata.create_all()`
  (`app/db/session.py`). No migration framework (no Alembic in
  `requirements.txt`). `upgrades/` is a reserved slot for one-off scripts
  (currently empty).
- **Why**: schema follows the models; no versioned-migration tooling exists.
- **Consequence**: schema changes = edit the model; never add migration files
  or "add" Alembic without changing this decision.

### Mixed query styles: 2.0 models + legacy CRUD
- **Choice**: models use SQLAlchemy 2.0 style (`Mapped[]` +
  `mapped_column()`); most CRUD/query code still uses legacy `db.query()`
  style.
- **Why**: the 2.0 adoption was partial — models moved first, query code
  didn't.
- **Consequence**: new query code must use `select()` (see BLOCK #2); convert
  legacy functions to `select()` when editing; never mix both styles in one
  function.
