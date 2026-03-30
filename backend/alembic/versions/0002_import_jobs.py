"""Add import jobs and row-level error tracking tables."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_import_jobs"
down_revision: Union[str, Sequence[str], None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    import_dataset = sa.Enum(
        "room_master",
        "request_code_rules",
        "reservations",
        "inventory_overrides",
        name="import_dataset",
    )
    import_job_status = sa.Enum("preview_ready", "committed", "failed", name="import_job_status")

    # Explicitly create PostgreSQL enum types once (idempotent with checkfirst=True).
    import_dataset.create(bind, checkfirst=True)
    import_job_status.create(bind, checkfirst=True)

    # Reuse existing types in table DDL without emitting CREATE TYPE again.
    import_dataset_column = sa.Enum(
        "room_master",
        "request_code_rules",
        "reservations",
        "inventory_overrides",
        name="import_dataset",
        create_type=False,
    )
    import_job_status_column = sa.Enum(
        "preview_ready",
        "committed",
        "failed",
        name="import_job_status",
        create_type=False,
    )

    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset", import_dataset_column, nullable=False),
        sa.Column("status", import_job_status_column, nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("valid_rows", sa.Integer(), nullable=False),
        sa.Column("invalid_rows", sa.Integer(), nullable=False),
        sa.Column("preview_rows_json", sa.JSON(), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_import_jobs"),
    )

    op.create_table(
        "import_job_errors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_job_id", sa.Integer(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("column_name", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"], name="fk_import_job_errors_import_job_id_import_jobs", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_import_job_errors"),
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_table("import_job_errors")
    op.drop_table("import_jobs")

    sa.Enum("preview_ready", "committed", "failed", name="import_job_status").drop(bind, checkfirst=True)
    sa.Enum("room_master", "request_code_rules", "reservations", "inventory_overrides", name="import_dataset").drop(bind, checkfirst=True)
