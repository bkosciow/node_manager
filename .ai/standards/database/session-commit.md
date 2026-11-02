# Session & Commit Contract

Every CRUD function takes `db: Session` as its first argument (injected by routes via the `get_db()` dependency) and returns SQLAlchemy model instances — not dicts or Pydantic objects.

Write-side CRUD follows `add → commit → refresh` inside the CRUD layer:

```python
def create_device(db: Session, data: DeviceCreate) -> Device:
    db_obj = Device(chip_id=data.chip_id, node=data.node)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj
```

- Read-only CRUD functions never commit.
- Route handlers don't commit — **exception (flexible):** a route that orchestrates multiple writes in one transaction may commit at the route level; it's an exception, not the default.
- Session factory: `sessionmaker(autocommit=False, autoflush=False, bind=engine)` — these flags are the FastAPI template default, not a hard invariant.
