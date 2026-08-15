from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_plan_public_id"
down_revision: str | Sequence[str] | None = "0021_plan_module"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("public_id", sa.String(length=32), nullable=True))
    op.execute("UPDATE plans SET public_id = substr(md5(random()::text || id::text), 1, 16)")
    op.alter_column("plans", "public_id", nullable=False)
    op.create_unique_constraint("uq_plans_public_id", "plans", ["public_id"])


def downgrade() -> None:
    op.drop_constraint("uq_plans_public_id", "plans", type_="unique")
    op.drop_column("plans", "public_id")
