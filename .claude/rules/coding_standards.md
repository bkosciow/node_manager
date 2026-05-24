# Coding Standards

Rules derived from the existing codebase. Follow these conventions when writing or modifying code.

## General

- **Line limit**: 100 characters (enforced by flake8 via `.flake8`).
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes/models.
- **Type hints**: Always annotate function parameters and return types. Use `type | None` (not `Optional[type]`).
- **Imports**: Use `from app.xxx` relative imports throughout the package (e.g., `from app.config import settings`).
- **Logging**: `logging.getLogger(__name__)`, with `basicConfig(level=logging.INFO)` at module entry points. Use `logger.info("msg %s", value)` style (not f-strings in log calls).
- **No magic defaults in code**: Configuration lives in `app/config.py` (`pydantic_settings.BaseSettings`). Read via the module-level `settings` singleton. Never hardcode URLs, ports, or paths in application code.

## FastAPI REST API (`rest_server.py`)

### Route definitions

```python
@app.get("/api/{resource}", response_model=list[ResourceResponse], tags=["resources"])
def list_resources(db: Session = Depends(get_db), token: str = Depends(verify_token)):
```

- Use `response_model` on every endpoint (the Pydantic Response schema).
- Group endpoints with `tags=["resource_name"]`.
- Declare tags in `openapi_tags` at FastAPI init for API docs.
- All route params after `db` and `token` use `Depends()`.

### Auth

- Every endpoint takes `token: str = Depends(verify_token)` from `app.auth`.
- `verify_token` uses `HTTPBearer(auto_error=False)` -- it gracefully skips when `API_TOKEN` is empty.
- Never bypass `verify_token` on an endpoint.

### CRUD endpoint pattern



### Query parameters

- Pagination: `skip: int = Query(0, ge=0)`, `limit: int = Query(100, ge=1, le=1000)`


### Nested resources

- Parent ID as path param: `/api/urls/{url_id}/patterns`
- Validate parent existence first (404 if missing), then proceed with child CRUD.

### Error responses

- 404: `HTTPException(status_code=404, detail="Resource not found")`
- 400: `HTTPException(status_code=400, detail="Invalid input: ...")`
- 409: `HTTPException(status_code=409, detail="Already exists")`
- DELETE success: return `{"message": "X deleted successfully"}` (not a Pydantic model).

### Inline JSON responses

For complex paginated outputs (patterns with embedded tags, discoveries with embedded source), build the dict manually and return `JSONResponse(...)` rather than using the `PaginatedResponse[T]` generic model. Include `total` and `current_page` in the payload.

## Pydantic Schemas (`app/schemas/`)

One file per resource. 

### Update models

- Every field is individually `Optional[type] = None`.
- Do NOT inherit from Base -- define standalone.
- Include ALL fields (even those in Base) so any field can be updated.

### Validators (Pydantic v2)

```python
@field_validator("field_name")
@classmethod
def validate_field_name(cls, v: str | None) -> str | None:
    ...
```

- Use `@field_validator` + `@classmethod`.
- If validation fails, raise `ValueError` with a descriptive message.
- Validators are duplicated on Create and Update models (not shared).

## SQLAlchemy Models (`app/models/`)

```python
class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(100), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- Always use `Mapped[type]` + `mapped_column()`.
- `id`: `primary_key=True, index=True`.
- String columns: always specify length (`String(255)`). `Text` for unbounded.
- Nullable columns: `Mapped[type | None]` + `nullable=True`.
- Boolean flags: `default=True`.
- Timestamps: `default=datetime.utcnow` (not `func.now()`).
- Relationships: use `back_populates` (bidirectional), string class references (`"Pattern"`).
- Parent-to-child: `cascade="all, delete-orphan"`.
- Foreign keys: `ForeignKey("tablename.column", ondelete="CASCADE")`.

### Association tables

- Defined in `app/db/relationships.py`, registered with `Base.metadata`.
- Use `ondelete="CASCADE"` on all foreign keys.

## CRUD Operations (`app/crud/`)

One file per resource. Re-exported via `crud/__init__.py`.

### Function signatures

| Function | Signature | Returns |
|----------|-----------|---------|
| get | `get_{res}(db: Session, {res}_id: int)` | `Optional[{Model}]` |
| list | `get_{resources}(db, skip, limit, active?)` | `list[{Model}]` or `tuple[list, int]` |
| create | `create_{res}(db, data: {Res}Create)` | `{Model}` |
| update | `update_{res}(db, {res}_id, data: {Res}Update)` | `Optional[{Model}]` |
| delete | `delete_{res}(db, {res}_id)` | `bool` |

### Create

```python
def create_resource(db: Session, data: ResourceCreate) -> Resource:
    db_obj = Resource(name=data.name, ...)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj
```

### Read single

```python
def get_resource(db: Session, resource_id: int) -> Optional[Resource]:
    return db.query(Resource).filter(Resource.id == resource_id).first()
```

### List

- Use conditional filtering: `if active is not None: query = query.filter(...)`
- Pagination: `.offset(skip).limit(limit).all()`
- For resources needing a total count: return `tuple[list, int]`, use `db.query(Model).count()`.
- Use `joinedload` for eager-loading relationships.
- String filtering: `Model.name.ilike(f"%{name}%")`.
- Many-to-many filtering: `.join(Model.tags).filter(Tag.id.in_(tag_ids)).distinct()`.

### Update (partial)

```python
def update_resource(db: Session, resource_id: int, data: ResourceUpdate) -> Optional[Resource]:
    obj = get_resource(db, resource_id)
    if obj is None:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj
```

- `model_dump(exclude_unset=True)` to get only provided fields.
- `setattr()` loop for dynamic updates.

### Delete

- Return `bool` (True/False, not the object).
- CRUD returns `None`/`False` for missing resources. The API layer raises `HTTPException`.

### Many-to-many handling

- Create: validate all IDs with `db.query(Model).filter(Model.id.in_(ids)).all()`, check for missing IDs, raise 400.
- Update: clear existing (`obj.tags = []`), then replace.

## Services (`app/services/`)

- Each service is a class with single-responsibility methods. No base class.
- Read config from `settings` singleton (imported from `app.config`).
- Use `requests` library for HTTP (not `httpx`).
- HTTP success check: `response.status_code > 299` (2xx = success, 3xx+ = failure).
- **Early return if disabled**: if a config value is empty (e.g., `settings.jellyfin_url`), return False immediately.
- Use `logging.getLogger(__name__)` for logging.
- Constructor: minimal setup (no HTTP calls in `__init__`).

### Private methods

Prefix internal/HTTP helper methods with `_` (e.g., `_request()`).

### Logging handler subclasses

Custom `logging.Handler` subclasses override `emit()`. Set level to `logging.ERROR` in `__init__`.


## Configuration (`app/config.py`)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./sources.db"
    app_host: str = "0.0.0.0"
    ...

    class Config:
        env_file = ".env"

settings = Settings()
```

- Use `pydantic_settings.BaseSettings`.
- All fields have defaults.
- Environment variable names are auto-derived (uppercased field names).
- Module-level singleton: `settings = Settings()`.
- Empty string = disabled for optional services (Apprise, Transmission, Jellyfin).

## Database (`app/db/`)

- `base.py`: single `declarative_base()`.
- `session.py`: `sessionmaker(autocommit=False, autoflush=False)`.
- `get_db()`: generator with `try/finally` to ensure session close.
- `init_db()`: calls `Base.metadata.create_all(bind=engine)`, invoked on FastAPI startup.
- No migrations: tables created via `create_all`.
- Script-level code (non-FastAPI) creates sessions manually with `try/finally`.

## File Organization



## Adding a New Resource

1. **Model**: Add to `app/models/` with `Mapped[]` columns, relationships, `__tablename__`.
2. **Schema**: Create `Base`, `Create`, `Update`, `Response` in `app/schemas/`.
3. **CRUD**: Add `get_*`, `create_*`, `update_*`, `delete_*`, `get_*_list` in `app/crud/`. Re-export from `__init__.py`.
4. **Routes**: Add CRUD endpoints to `rest_server.py` following the standard pattern.
5. **Register**: Add model import to `models/__init__.py`, CRUD functions to `crud/__init__.py`.

