# ADR-005: JSON Column for Event Parameters

## Status
Accepted

## Date
2026-06-07

## Context
Event parameters have an unknown, varying structure — pong returns system stats, hash events return file:hash mappings. We need to store them as-is without schema enforcement.

## Decision
We will use SQLAlchemy's `JSON` type for the `parameters` column on `DeviceEvent`. On MySQL, this maps to the native `JSON` column type, which provides efficient storage and built-in validation.

## Consequences

### Positive
- Native MySQL JSON — efficient storage, automatic validation on insert
- SQLAlchemy handles dict ↔ JSON serialization transparently
- No schema migration needed when device firmware adds new fields
- Queryable via MySQL JSON functions if needed in the future

### Negative
- MySQL-specific — if we migrate to PostgreSQL, column type changes from `JSON` to `JSONB`
- No type safety on the parameters content — must be handled at application layer if validation is needed

### Risks
- **Risk**: Large JSON payloads could exceed MySQL row size limits (65KB for InnoDB).
  **Mitigation**: Current payloads are <1KB. If this changes, add a size check in the handler.

## Alternatives Considered
1. **TEXT column with manual JSON serialization**: Works everywhere, but loses native JSON validation and queryability. Rejected — MySQL JSON is better.
2. **EAV (Entity-Attribute-Value) table**: Normalized, but requires N rows per event and complex queries to reconstruct. Rejected — overkill for unknown structure.
3. **Fixed schema per event type**: One column per known field. Rejected — structure is unknown and varies by firmware version.
