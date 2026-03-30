from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import TimestampMixin


class ReservationRequest(TimestampMixin, Base):
    __tablename__ = "reservation_requests"
    __table_args__ = (UniqueConstraint("reservation_id", "request_code", name="uq_reservation_requests_reservation_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False)
    request_code: Mapped[str] = mapped_column(String(50), nullable=False)
    request_value: Mapped[str | None] = mapped_column(String(255))
