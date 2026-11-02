# Query Style & Model Conventions

**New query code must use SQLAlchemy 2.0-style `select()`.** Existing CRUD code still uses legacy `db.query(Model)` style — it's debt slated for refactoring, not a style to copy:

```python
# target style for new code
def get_device(db: Session, device_id: int) -> Device | None:
    stmt = select(Device).where(Device.id == device_id)
    return db.execute(stmt).scalar_one_or_none()
```

- Don't bulk-refactor legacy `db.query()` calls in files you're not otherwise touching — but convert a function to `select()` when you're already editing it.
- Legacy→2.0 mapping: `.first()` → `db.execute(stmt).scalar_one_or_none()`, `.all()` → `db.execute(stmt).scalars().all()`.
- Models use 2.0-style `Mapped[...]` + `mapped_column()` — never mix in old `Column()`.
- PKs: `mapped_column(Integer, primary_key=True, index=True)`. Uniqueness lives in named `UniqueConstraint`s in `__table_args__` with `uq_`-prefixed names — name new ones the same.
- FK delete behavior is a **per-model choice** (existing models all use `ondelete="CASCADE"` + `cascade="all, delete-orphan"` on the parent). Pick delete behavior deliberately for new FKs.
- Eager-load parent→child reads with `joinedload(Model.child_rel)`; lazy loading is the default.
- Cross-model relationships that would create import cycles: import under `TYPE_CHECKING`, use the string relationship name, and add `# noqa: F821` on the relationship line.
