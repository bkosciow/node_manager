# Error Responses

Use `HTTPException` with a `detail` string — no custom error codes.

```python
raise HTTPException(status_code=404, detail="Device not found")
raise HTTPException(status_code=400, detail=f"Invalid repo type: {repo_type}")
```

| Status | When |
|--------|------|
| 400 | Invalid input, unsupported values |
| 403 | Auth token mismatch (from `verify_token`) |
| 404 | Resource not found |
| 422 | Query param validation (FastAPI auto-generates) |

- Never bypass `verify_token` on an endpoint
- DELETE success: return `{"message": "X deleted successfully"}`
