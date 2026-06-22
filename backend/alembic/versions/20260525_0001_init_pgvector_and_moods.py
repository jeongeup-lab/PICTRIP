"""init: pgvector extension + moods seed

Revision ID: 0001_init
Revises:
Create Date: 2026-05-25 00:00:00

The first migration intentionally does only two things:
1. CREATE EXTENSION vector (pgvector) — required by IMG/USR vector columns.
2. Create the `moods` reference table and seed the 8 base moods.

All other tables land in subsequent migrations authored by Dev B during Week 2.
This split lets Dev B autogenerate later migrations without re-introducing the
extension creation each time.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_init"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_MOODS_SEED = [
    (1, "sea", "바다", "🌊", 1),
    (2, "mountain", "산·숲", "⛰️", 2),
    (3, "lake", "호수", "🏞️", 3),
    (4, "island", "섬", "🏝️", 4),
    (5, "hanok", "한옥·고궁", "🏛️", 5),
    (6, "night", "야경", "🌃", 6),
    (7, "market", "시장", "🛍️", 7),
    (8, "street", "도시 골목", "🏙️", 8),
]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    moods = op.create_table(
        "moods",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        sa.Column("code", sa.String(16), nullable=False, unique=True),
        sa.Column("name", sa.String(32), nullable=False),
        sa.Column("emoji", sa.String(8), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False),
    )

    op.bulk_insert(
        moods,
        [
            {"id": i, "code": c, "name": n, "emoji": e, "sort_order": s}
            for i, c, n, e, s in _MOODS_SEED
        ],
    )


def downgrade() -> None:
    op.drop_table("moods")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS vector")
