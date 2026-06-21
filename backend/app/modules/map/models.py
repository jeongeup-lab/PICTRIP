"""MAP ORM models.

The MAP domain has no persistent tables: nearby spots come from the KTO
locationBasedList2 API and live crowd data lives in Redis. The former
`region_visitors` / `sigungu_visitors` DataLab tables were never read or written
by any service and were dropped in migration 0010.

This module is intentionally empty of models; `alembic/env.py` still imports it
for symmetry with the other domains.
"""

from __future__ import annotations
