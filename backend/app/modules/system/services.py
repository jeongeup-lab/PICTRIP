"""SYS service layer.

Notifications and analytics ingest were removed in the refactor (S10): the
`notifications` / `analytics_events` tables are dropped in Stage B (M4). The only
remaining system surface is the static `/meta/version` endpoint, which needs no
service logic.
"""

from __future__ import annotations
