"""Add assignment engine fields for run typing and explanation outputs."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_assignment_engine_fields"
down_revision: Union[str, Sequence[str], None] = "0002_import_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("assignment_runs", sa.Column("run_type", sa.String(length=32), server_default="type-balance", nullable=False))
    op.add_column("assignment_results", sa.Column("reason_codes", sa.JSON(), server_default="[]", nullable=False))
    op.add_column("assignment_results", sa.Column("request_misses", sa.JSON(), server_default="[]", nullable=False))
    op.add_column("assignment_results", sa.Column("manual_review_flags", sa.JSON(), server_default="[]", nullable=False))


def downgrade() -> None:
    op.drop_column("assignment_results", "manual_review_flags")
    op.drop_column("assignment_results", "request_misses")
    op.drop_column("assignment_results", "reason_codes")
    op.drop_column("assignment_runs", "run_type")
