# Authentication

Every endpoint requires `token: str = Depends(verify_token)` from `app.auth`.

```python
@app.get("/api/devices", response_model=list[DeviceResponse], tags=["devices"])
def list_devices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
):
    ...
```

- `verify_token` uses `HTTPBearer(auto_error=False)` — skips validation when `API_TOKEN` env var is empty
- Returns `403` on token mismatch
- `/health` is public (no auth) — other public endpoints may exist but are rare
- Never bypass `verify_token` without explicit reason
