# Route Parameter Order

Route handler parameters follow a strict order:

1. Path params (declared in `@app.get("...")` decorator, typed with `Path()`)
2. Query params (typed with `Query()`)
3. Body params (Pydantic model, e.g. `body: RepoAssignmentCreate = ...`) — directly after path/query params, before `db` (see `assign_repo`, `add_ignored_file`)
4. `db: Session = Depends(get_db)`
5. `token: str = Depends(verify_token)`

```python
@app.get("/api/devices/{device_id}", tags=["devices"])
def get_single_device(
    device_id: int = Path(ge=1),           # path param
    db: Session = Depends(get_db),          # DB dependency
    token: str = Depends(verify_token),     # auth dependency
):
    ...
```

- Pagination: `skip: int = Query(0, ge=0)`, `limit: int = Query(100, ge=1, le=1000)`
- Group endpoints with `tags=["resource_name"]`
