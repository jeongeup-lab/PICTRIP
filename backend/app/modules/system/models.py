"""SYS ORM models.

The `notifications` and `analytics_events` tables were removed in the refactor
(S10). Their ORM classes are deleted so Alembic autogenerate emits the drops in
Stage B (M4); the tables remain orphan in the DB until that migration is applied.
No system-owned ORM models remain.
"""

from __future__ import annotations
