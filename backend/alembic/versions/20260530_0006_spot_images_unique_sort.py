"""SPT: unique (content_id, sort_order) on spot_images

Revision ID: 0006_spot_images_unique_sort
Revises: 0005_schema_v1_2_alignment
Create Date: 2026-05-30 00:00:00

Supports the lazy spot-detail image cache (Gap B / ADR-0007): detailImage2
results are upserted by (content_id, sort_order), so that key must be unique.
spot_images is empty at this point, so adding the constraint is safe.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006_spot_images_unique_sort"
down_revision: str | Sequence[str] | None = "0005_schema_v1_2_alignment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_spot_images_content_sort",
        "spot_images",
        ["content_id", "sort_order"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_spot_images_content_sort", "spot_images", type_="unique")
