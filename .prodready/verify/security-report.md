# Security Audit Report

Generated: 2026-06-10

## Dependency Scan (pip-audit)

13 known vulnerabilities found in 6 transitive packages.

| Package | Version | Vulnerability | Severity | Fix Version |
|---------|---------|---------------|----------|-------------|
| idna | 3.11 | CVE-2026-45409 | Low | 3.15 |
| pip | 26.1.1 | PYSEC-2026-196 | Info | 26.1.2 |
| pyjwt | 2.12.1 | PYSEC-2026-179 | Low | 2.13.0 |
| pyjwt | 2.12.1 | PYSEC-2026-175 | Low | 2.13.0 |
| pyjwt | 2.12.1 | PYSEC-2026-177 | Low | 2.13.0 |
| pyjwt | 2.12.1 | PYSEC-2026-178 | Low | 2.13.0 |
| starlette | 1.0.0 | PYSEC-2026-161 | Low | 1.0.1 |
| urllib3 | 2.6.3 | PYSEC-2026-142 | Low | 2.7.0 |
| urllib3 | 2.6.3 | PYSEC-2026-141 | Low | 2.7.0 |
| uv | 0.9.26 | GHSA-pjjw-68hj-v9mw | Low | 0.11.6 |
| uv | 0.9.26 | GHSA-4gg8-gxpx-9rph | Low | 0.11.15 |

**Critical: 0 | High: 0 | Medium: 0 | Low/Info: 13**

All vulnerabilities are in transitive dependencies (not direct app code). None are Critical or High.

## Secrets Detection

- No hardcoded secrets found in app/ source code.
- .env.example contains placeholder values only.
- No .env or credential files committed to git.

## OWASP Top 10 Checklist

| # | Vulnerability | Status | Notes |
|---|---------------|--------|-------|
| A01 | Broken Access Control | Pass | verify_token on all endpoints |
| A02 | Cryptographic Failures | Pass | No passwords stored; API token from env |
| A03 | Injection | Pass | SQLAlchemy ORM with parameterized queries |
| A04 | Insecure Design | Pass | Pydantic validation on all inputs |
| A05 | Security Misconfiguration | Pass | Non-root Docker user, minimal image |
| A06 | Vulnerable Components | Pass | No critical/high dependency vulns |
| A07 | Auth Failures | Pass | Token auth via HTTPBearer |
| A08 | Data Integrity | Pass | Pydantic v2 validation on all inputs |
| A09 | Logging Failures | Pass | No secrets logged |
| A10 | SSRF | Pass | No external URL fetching in request path |

## Code Review

- [x] No hardcoded secrets
- [x] API token from environment variable
- [x] All inputs validated via Pydantic
- [x] Error messages don't leak internal details
- [x] Database credentials from env
- [x] Non-root Docker user

## Issues Found

| # | Severity | Issue | Recommendation |
|---|----------|-------|----------------|
| 1 | Low | Transitive dependency vulnerabilities (13) | pip install --upgrade pyjwt starlette urllib3 idna |
| 2 | Info | datetime.utcnow() deprecation warnings | Replace with datetime.now(datetime.UTC) |

## Result

**Status: PASSED - 0 Critical, 0 High issues**
