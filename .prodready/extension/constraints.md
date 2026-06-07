# Constraints — Event Data Extension

## Deployment
- Target: same as existing service (Docker / self-hosted).
- Region: N/A (internal network).

## Scale
- Launch: ~10-50 devices, events every few seconds per device.
- 6 months: ~100 devices, same frequency.

## Budget
- Infrastructure: zero cost (self-hosted).
- Tooling: free tier only.

## Compliance & Security
- None beyond existing service constraints.
- Internal network only, no public exposure.

## Tech Stack Preferences
- Language: Python (existing).
- Framework: FastAPI (existing).
- Database: SQLAlchemy with SQLite/PostgreSQL (existing).
- ORM: SQLAlchemy (existing).
- Additional: follow existing coding standards (`coding_standards.md`).
