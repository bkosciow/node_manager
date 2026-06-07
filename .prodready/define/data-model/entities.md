# Data Model

## Entities

### Device
- id: int (auto-increment primary key)
- chip_id: str (unique device identifier from message)
- node: str (device name, not unique)
- created_at: datetime (timestamp of first discovery)

## Relationships
No relationships — single entity for MVP.

## Indexes
- (chip_id, node) — unique composite (enforces no duplicates)
- id — primary key (auto-indexed)
