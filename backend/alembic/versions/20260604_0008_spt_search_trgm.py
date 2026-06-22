"""SPT: pg_trgm GIN indexes for free-text spot search

Revision ID: 0008_spt_search_trgm
Revises: 0007_usr_sessions_devices
Create Date: 2026-06-04 00:00:00

Backs ``GET /v1/spots/search`` (지명·장소 ILIKE on title/addr1). A leading-wildcard
``ILIKE '%q%'`` cannot use a btree, so without trigram support every keystroke is
a sequential scan over the active spot set (~68k rows). The ``pg_trgm`` GIN
indexes make the substring match index-assisted. Indexes are partial
(``WHERE show_flag = 1``) to match the user-facing search predicate, consistent
with the active partial-index convention (ADR-0007).

pg_trgm is a standard contrib extension present in the pgvector image used by CI
and the home-server Postgres.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008_spt_search_trgm"
down_revision: str | Sequence[str] | None = "0007_usr_sessions_devices"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_spots_title_trgm "
        "ON spots USING gin (title gin_trgm_ops) "
        "WHERE show_flag = 1"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_spots_addr1_trgm "
        "ON spots USING gin (addr1 gin_trgm_ops) "
        "WHERE show_flag = 1"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_spots_addr1_trgm")
    op.execute("DROP INDEX IF EXISTS idx_spots_title_trgm")
    # Leave the pg_trgm extension in place: other objects may depend on it and
    # dropping an extension is rarely what a downgrade wants.
