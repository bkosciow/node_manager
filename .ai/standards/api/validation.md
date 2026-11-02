# Validation

Validate parent/child existence before any operation — raise 404 if missing.

```python
@app.post("/api/nodes/{device_id}/repos", tags=["assignments"])
def assign_repo(
    device_id: int = Path(ge=1),
    body: RepoAssignmentCreate = ...,
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
):
    device = get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    repo = get_repository(db, body.repository_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Now safe to proceed
    assignment = assign_repo_to_node(db, device_id, body.repository_id, repo.repo_type)
```

- Parent path param (device_id) → check exists first
- Child reference (repository_id from body) → check exists second
- Then perform the operation
- Schema validators (`@field_validator`) handle field-level validation (non-empty strings, etc.)
- Path params use `Path(ge=1)` for ID validation
