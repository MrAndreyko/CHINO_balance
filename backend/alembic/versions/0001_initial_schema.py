"""Initial schema for hotel room balancing service."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("room_number", sa.String(length=50), nullable=False),
        sa.Column("room_type", sa.String(length=50), nullable=False),
        sa.Column("floor", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_rooms"),
        sa.UniqueConstraint("room_number", name="uq_rooms_room_number"),
    )
    op.create_index("ix_rooms_room_number", "rooms", ["room_number"], unique=True)

    op.create_table(
        "reservations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("guest_name", sa.String(length=255), nullable=False),
        sa.Column("arrival_date", sa.Date(), nullable=False),
        sa.Column("departure_date", sa.Date(), nullable=False),
        sa.Column("requested_room_type", sa.String(length=50), nullable=False),
        sa.Column("assigned_room_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assigned_room_id"], ["rooms.id"], name="fk_reservations_assigned_room_id_rooms", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_reservations"),
        sa.UniqueConstraint("external_id", name="uq_reservations_external_id"),
    )
    op.create_index("ix_reservations_external_id", "reservations", ["external_id"], unique=True)

    op.create_table(
        "request_code_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("default_weight", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_request_code_rules"),
        sa.UniqueConstraint("code", name="uq_request_code_rules_code"),
    )
    op.create_index("ix_request_code_rules_code", "request_code_rules", ["code"], unique=True)

    op.create_table(
        "weights_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_weights_config"),
        sa.UniqueConstraint("key", name="uq_weights_config_key"),
    )
    op.create_index("ix_weights_config_key", "weights_config", ["key"], unique=True)

    op.create_table(
        "compatibility_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("is_compatible", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_compatibility_rules"),
        sa.UniqueConstraint("source_type", "target_type", name="uq_compatibility_source_target"),
    )

    op.create_table(
        "assignment_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_status", sa.String(length=32), nullable=False),
        sa.Column("triggered_by", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_assignment_runs"),
    )

    op.create_table(
        "reservation_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("request_code", sa.String(length=50), nullable=False),
        sa.Column("request_value", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"], name="fk_reservation_requests_reservation_id_reservations", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_reservation_requests"),
        sa.UniqueConstraint("reservation_id", "request_code", name="uq_reservation_requests_reservation_code"),
    )

    op.create_table(
        "inventory_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("override_date", sa.Date(), nullable=False),
        sa.Column("capacity_delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], name="fk_inventory_overrides_room_id_rooms", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_inventory_overrides"),
    )

    op.create_table(
        "manual_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("applied_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"], name="fk_manual_overrides_reservation_id_reservations", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], name="fk_manual_overrides_room_id_rooms", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_manual_overrides"),
    )

    op.create_table(
        "assignment_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assignment_run_id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("rationale", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assignment_run_id"], ["assignment_runs.id"], name="fk_assignment_results_assignment_run_id_assignment_runs", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"], name="fk_assignment_results_reservation_id_reservations", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.id"], name="fk_assignment_results_room_id_rooms", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_assignment_results"),
        sa.UniqueConstraint("assignment_run_id", "reservation_id", name="uq_assignment_result_run_reservation"),
    )


def downgrade() -> None:
    op.drop_table("assignment_results")
    op.drop_table("manual_overrides")
    op.drop_table("inventory_overrides")
    op.drop_table("reservation_requests")
    op.drop_table("assignment_runs")
    op.drop_table("compatibility_rules")
    op.drop_index("ix_weights_config_key", table_name="weights_config")
    op.drop_table("weights_config")
    op.drop_index("ix_request_code_rules_code", table_name="request_code_rules")
    op.drop_table("request_code_rules")
    op.drop_index("ix_reservations_external_id", table_name="reservations")
    op.drop_table("reservations")
    op.drop_index("ix_rooms_room_number", table_name="rooms")
    op.drop_table("rooms")
