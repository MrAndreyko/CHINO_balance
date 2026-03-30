from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import TimestampMixin


class AssignmentResult(TimestampMixin, Base):
    __tablename__ = "assignment_results"
    __table_args__ = (UniqueConstraint("assignment_run_id", "reservation_id", name="uq_assignment_result_run_reservation"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_run_id: Mapped[int] = mapped_column(ForeignKey("assignment_runs.id", ondelete="CASCADE"), nullable=False)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False)
    room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id", ondelete="SET NULL"))
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rationale: Mapped[str | None] = mapped_column(String(500))
