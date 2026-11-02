---
name: discover-standards-2026-06-19
description: First /discover-standards run — 5 API standards created
metadata:
  type: project
---

On 2026-06-19, ran /discover-standards focusing on API Routes. Created 5 standards:

- [[api-auth]] — verify_token middleware, /health is public
- [[api-error-responses]] — HTTPException + detail strings, no error codes
- [[api-response-format]] — no envelope, mixed response_model usage
- [[api-route-params]] — strict param order: path → query → db → token → body
- [[api-validation]] — validate parent/child existence before operations

**Why:** These are the standards most likely to be violated when agents add new endpoints.

**How to apply:** Inject these standards before implementing any new API endpoint. Remaining areas not yet documented: Database/CRUD, Testing, Background Workers.
