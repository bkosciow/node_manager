# None + IntegrityError Contract

CRUD functions stay transport-agnostic: they return `None` when a row or parent is missing and let constraint violations propagate — no HTTP semantics inside CRUD. Routes translate.

- `None` → `HTTPException(404)`:
  ```python
  assignment = assign_repo_to_node(db, device_id, repo_id, repo_type)
  if assignment is None:
      raise HTTPException(status_code=404, detail="Assignment failed")
  ```
- Duplicates: `create_ignored_file` propagates the constraint violation; the route catches the broad exception and **string-matches on `"UNIQUE constraint failed"`** in `str(exc)` → 409. Keep this shape; the `uq_device_repo_filename` constraint is the final guard.
- `get_or_create_device` is the only get-or-create with a race guard: check → create → on `IntegrityError`: `db.rollback()` and re-fetch. Specific to device discovery (concurrent UDP inserts). Other upserts (`upsert_event`, `upsert_repository_file`) run single-threaded and rely on named `uq_*` constraints alone as the final guard.
