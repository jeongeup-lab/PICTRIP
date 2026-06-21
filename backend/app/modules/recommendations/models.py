"""REC ORM models.

The REC domain has no persistent tables: `today-inspo` recommendations are
computed on the fly and cached in Redis, and `find_similar_spots` reads SPT/IMG
data via their services. The former `recommendation_logs` / `reason_cache`
tables (a schema-ahead-of-code bet on an ML ranker + LLM reason cache) were
never wired into any service and were dropped in migration 0010.

This module is intentionally empty of models; `alembic/env.py` still imports it
for symmetry with the other domains.
"""

from __future__ import annotations
