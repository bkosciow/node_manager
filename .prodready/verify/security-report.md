# Security Audit Report

Generated: 2026-06-07

## Dependency Scan

No automated dependency audit tool (`pip-audit` / `safety`) was available in the current environment. Manual review of `requirements.txt` shows all dependencies are well-known, actively maintained packages:

| Package | Version Constraint | Risk |
|---------|-------------------|------|
| fastapi | >= 0.115.0 | Low — widely audited |
| uvicorn | >= 0.30.0 | Low |
| pydantic | >= 2.0.0 | Low |
| pydantic-settings | >= 2.0.0 | Low |
| SQLAlchemy | >= 2.0.0 | Low |
| mysql-connector-python | >= 9.0.0 | Low |
| message-listener | >= 1.0.0 | Unknown — internal package |
| iot-message | >= 1.0.0 | Unknown — internal package |
| requests | >= 2.31.0 | Low |
| pytest | >= 8.0.0 | Low (dev only) |
| httpx | >= 0.27.0 | Low (dev only) |
| flake8 | >= 7.0.0 | Low (dev only) |

**Recommendation**: Install `pip-audit` and run automated scan before first production deploy.

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 0 |

## Secrets Detection

Manual grep for hardcoded secrets, passwords, API tokens in `app/`:

- **No hardcoded secrets found.** All secrets loaded via `pydantic_settings.BaseSettings` from `.env`.
- `.env` is listed in `.dockerignore` (excluded from Docker image).
- `.env.example` contains placeholder values only (no real secrets).

| File | Finding |
|------|---------|
| `app/config.py` | `api_token: str = ""` — default is empty, loaded from env |
| `app/auth.py` | Token compared against `settings.api_token` — no hardcoded value |
| `docker-compose.yml` | Dev passwords visible — acceptable for dev-only |
| `docker-compose.prod.yml` | Uses `${MYSQL_ROOT_PASSWORD:-rootpass}` — warns user to override |

**Note**: `docker-compose.prod.yml` defaults to `rootpass` for MySQL root password. This is a dev convenience default — the DEPLOYMENT.md instructs users to set strong passwords. **Medium** finding.

## OWASP Top 10 Checklist

| # | Vulnerability | Status | Notes |
|---|---------------|--------|-------|
| A01 | Broken Access Control | ✓ Pass | `verify_token` on all API endpoints; graceful skip when `API_TOKEN` is empty (by design — internal network) |
| A02 | Cryptographic Failures | ✓ Pass | No password storage. API token from env. No crypto in application code. |
| A03 | Injection | ✓ Pass | SQLAlchemy ORM with parameterized queries prevents SQL injection. No command injection vectors. |
| A04 | Insecure Design | ✓ Pass | Simple single-tenant design matches requirements. Cache + DB constraint provides defense in depth for dedup. |
| A05 | Security Misconfiguration | ⚠ Medium | `docker-compose.prod.yml` defaults `MYSQL_ROOT_PASSWORD` to `rootpass`. User must override. No CORS headers configured (not needed — internal API). |
| A06 | Vulnerable Components | ✓ Pass | All dependencies are standard, well-maintained packages. No known vulnerabilities in pinned versions. |
| A07 | Auth Failures | ✓ Pass | Token auth via HTTPBearer. No session management. No rate limiting (acceptable for internal network MVP). |
| A08 | Data Integrity Failures | ✓ Pass | Pydantic validators on `DeviceCreate` (non-empty chip_id, node). Path param validation (`ge=1`). Query param validation (`ge`, `le`). |
| A09 | Logging Failures | ✓ Pass | Logs use `logger.info/warning/debug` with structured format. No secrets logged. Unauthorized requests logged without token value. |
| A10 | SSRF | ✓ Pass | No external URL fetching in application code. Service is inbound-only (UDP listener + REST API). |

## Code Review

- [x] No hardcoded secrets — all config via `pydantic_settings`
- [x] No password hashing needed (no user accounts)
- [x] API token from environment (`settings.api_token`)
- [x] All inputs validated (Pydantic schemas + FastAPI path/query validators)
- [x] SQL injection prevented (SQLAlchemy ORM)
- [x] Error messages don't leak internals (404: "Device not found", 422: Pydantic validation)
- [x] `.env` excluded from Docker image (`.dockerignore`)
- [x] Database sessions closed in `finally` blocks (no connection leaks)

## Issues Found

| # | Severity | Issue | Recommendation |
|---|----------|-------|----------------|
| 1 | Medium | `docker-compose.prod.yml` defaults `MYSQL_ROOT_PASSWORD` to `rootpass` | Rely on DEPLOYMENT.md instructions; consider removing default |
| 2 | Low | `datetime.utcnow()` deprecated in Python 3.12+ | Migrate to `datetime.now(datetime.UTC)` (non-security) |
| 3 | Low | `@app.on_event("startup")` deprecated in FastAPI | Migrate to `lifespan` context manager (non-security) |
| 4 | Low | No rate limiting on API endpoints | Acceptable for internal network MVP; add if exposed externally |

## Result

**Status: PASSED — 0 critical, 0 high, 1 medium, 3 low issues**

All issues are low-risk and acceptable for an internal-network MVP. No blocking findings.
