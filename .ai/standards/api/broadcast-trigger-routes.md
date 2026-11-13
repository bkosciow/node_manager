# Broadcast Trigger Routes

REST routes that make the manager actively ask a node for something
(upgrade broadcast, liveness ping, on-demand hash report) share one shape.

## Guard order

1. Input validation — `400` (e.g., `repo_type` not in `VALID_REPO_TYPES`)
2. Resource existence — `404` "Device not found"
3. Route-specific checks (e.g., `/update`'s assignment + diff 404s) slot in here
4. Broadcast capability — `503` "Node listener not configured" when
   `settings.node_listener` is empty
5. `comm.send(payload)` — the actual UDP broadcast
6. Return `202` with a hand-built dict

## Shape

```python
@app.post(
    "/api/devices/{device_id}/rescan/{repo_type}",
    status_code=202,
    tags=["device-queries"],
)
def rescan_device(
    device_id: int = Path(ge=1),
    repo_type: str = Path(),
    db: Session = Depends(get_db),
    token: str = Depends(verify_token),
) -> dict:
    if repo_type not in VALID_REPO_TYPES:
        raise HTTPException(status_code=400, detail="Invalid repository type")

    device = get_device(db, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    if not settings.node_listener:
        raise HTTPException(status_code=503, detail="Node listener not configured")

    comm.send({"event": f"system.{repo_type}.get_hash", "targets": [device.node]})
    return {
        "message": "Rescan broadcast sent",
        "event": f"system.{repo_type}.get_hash",
        "target": device.node,
    }
```

Rules:

- **202, not 200** — the route enqueues a broadcast; delivery to the node is
  async and fire-and-forget. The node's reply is ingested passively by the
  UDP listener (`messaging/message-handler`), never by the route.
- **No `response_model`** — hand-built dict `{"message", "event", "target"}`
  (`api/response-format`).
- **503 guard is mandatory** — an empty `NODE_LISTENER` means there is no
  broadcast target; fail loudly instead of silently no-op'ing.
- **UDP payload is `{"event", "targets"}` only**, unless the event needs
  `parameters` (`trigger_device_update` adds `parameters` for the upgrade
  diff; ping/rescan do not).
- **No repository assignment required** — ping/rescan work for any device;
  only `/update` 404s without a matching assignment.

Occurrences: `trigger_device_update`, `ping_device`, `rescan_device`
(all in `app/rest_server.py`).
