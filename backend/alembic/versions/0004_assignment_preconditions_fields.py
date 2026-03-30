"""Strengthen room/reservation/inventory fields for assignment preconditions."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_assignment_preconditions_fields"
down_revision: Union[str, Sequence[str], None] = "0003_assignment_engine_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("rooms", sa.Column("bed_type", sa.String(length=32), server_default="unknown", nullable=False))
    op.add_column("rooms", sa.Column("is_hardblocked", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("rooms", sa.Column("is_accessible", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("rooms", sa.Column("is_near_elevator", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("rooms", sa.Column("is_club_floor", sa.Boolean(), server_default=sa.text("false"), nullable=False))

    op.add_column("reservations", sa.Column("requested_bed_type", sa.String(length=32), server_default="unknown", nullable=False))
    op.add_column("reservations", sa.Column("chain_id", sa.String(length=64), nullable=True))
    op.add_column("reservations", sa.Column("linked_reservation_id", sa.Integer(), nullable=True))
    op.add_column("reservations", sa.Column("club_access_entitled", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.create_foreign_key(
        "fk_reservations_linked_reservation_id_reservations",
        "reservations",
        "reservations",
        ["linked_reservation_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("inventory_overrides", sa.Column("status", sa.String(length=32), server_default="open", nullable=False))


def downgrade() -> None:
    op.drop_column("inventory_overrides", "status")

    op.drop_constraint("fk_reservations_linked_reservation_id_reservations", "reservations", type_="foreignkey")
    op.drop_column("reservations", "club_access_entitled")
    op.drop_column("reservations", "linked_reservation_id")
    op.drop_column("reservations", "chain_id")
    op.drop_column("reservations", "requested_bed_type")

    op.drop_column("rooms", "is_club_floor")
    op.drop_column("rooms", "is_near_elevator")
    op.drop_column("rooms", "is_accessible")
    op.drop_column("rooms", "is_hardblocked")
    op.drop_column("rooms", "bed_type")
