from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import TimestampMixin


class Room(TimestampMixin, Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    room_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    room_type: Mapped[str] = mapped_column(String(50), nullable=False)
    bed_type: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    floor: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_hardblocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_accessible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_near_elevator: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_club_floor: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
