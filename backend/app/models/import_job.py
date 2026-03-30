from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.common import TimestampMixin


class ImportDataset(str, Enum):
    ROOM_MASTER = "room_master"
    REQUEST_CODE_RULES = "request_code_rules"
    RESERVATIONS = "reservations"
    INVENTORY_OVERRIDES = "inventory_overrides"


class ImportJobStatus(str, Enum):
    PREVIEW_READY = "preview_ready"
    COMMITTED = "committed"
    FAILED = "failed"


class ImportJob(TimestampMixin, Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset: Mapped[ImportDataset] = mapped_column(SQLEnum(ImportDataset, name="import_dataset"), nullable=False)
    status: Mapped[ImportJobStatus] = mapped_column(
        SQLEnum(ImportJobStatus, name="import_job_status"), default=ImportJobStatus.PREVIEW_READY, nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    preview_rows_json: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ImportJobError(TimestampMixin, Base):
    __tablename__ = "import_job_errors"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    column_name: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
