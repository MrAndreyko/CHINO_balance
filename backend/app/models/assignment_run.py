from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import TimestampMixin


class AssignmentRun(TimestampMixin, Base):
    __tablename__ = "assignment_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_type: Mapped[str] = mapped_column(String(32), default="type-balance", nullable=False)
    run_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    triggered_by: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    notes: Mapped[str | None] = mapped_column(String(255))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
