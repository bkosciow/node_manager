# Entity Triple & Naming

Every new entity gets ALL THREE files:

- `app/models/<entity>.py` — SQLAlchemy 2.0 model
- `app/crud/<entity>.py` — get_/create_/upsert_/delete_ functions
- `app/schemas/<entity>.py` — `<Entity>Create` / `<Entity>Response`

Plus: add the model to `app/models/__init__.py` (import + `__all__`) —
`Base.metadata.create_all` and test `create_all` only know tables that
are imported there.

Barrel re-exports:

- `app/models/__init__.py` and `app/crud/__init__.py` re-export
  everything with `__all__`.
- `app/schemas/__init__.py` is empty (historical accident) — target
  state: schemas also gets a barrel. Until then, import schemas from
  their module (`from app.schemas.device import DeviceCreate`).

Naming:

- `__tablename__`: plural snake_case (`devices`, `device_events`)
- Unique constraint names: `uq_` prefix (`uq_chip_id_node`) — see
  `database/query-style`
- CRUD functions: verb-first snake_case (`get_device`, `get_devices`,
  `create_device`, `upsert_event`, `get_or_create_device`)
- Schemas: `<Entity>Create`, `<Entity>Response`; ORM-backed responses
  set `model_config = {"from_attributes": True}`
- Relationships: string forward-ref class names + `TYPE_CHECKING`
  import + `# noqa: F821`; owned children use
  `cascade="all, delete-orphan"`
- New models carry `created_at: Mapped[datetime]` with
  `default=datetime.utcnow` (matches existing models)
