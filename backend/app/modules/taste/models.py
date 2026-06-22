"""TST ORM models.

The TST domain has no persistent tables: photo search runs CLIP in memory
(user bytes are never stored, a KTO compliance requirement) and queries IMG
neighbours via its service. The former `user_mood_preferences` /
`taste_feedback_events` tables (a bet on a personalised taste vector that never
shipped) were never read or written by any service and were dropped in
migration 0010.

This module is intentionally empty of models; `alembic/env.py` still imports it
for symmetry with the other domains.
"""

from __future__ import annotations
