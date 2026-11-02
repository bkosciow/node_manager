# Config Settings (app/config.py)

- Import the module-level singleton: `from app.config import settings` —
  never construct `Settings()` yourself.
- Fields: snake_case, pydantic types, `.env`-driven via
  `class Config: env_file = ".env"`.
- "Feature off" flag pattern (case-by-case, established for these three
  — NOT a general contract): `api_token`, `apprise_url` (+`apprise_tag`),
  `sl_passphrase` default to empty string, which means the feature is
  disabled; code gates on `if not settings.x`. Don't assume a new field
  follows this pattern without confirming.
- `database_url` defaults to empty but is REQUIRED in every deployment —
  it must be set in `.env` (see `.env.example`).
- Adding a new settings field: add it to `Settings` and document it in
  `.env.example`.
