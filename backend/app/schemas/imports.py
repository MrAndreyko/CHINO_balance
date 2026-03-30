from datetime import datetime

from pydantic import BaseModel

from app.models.import_job import ImportDataset, ImportJobStatus


class RowError(BaseModel):
    row_number: int
    column_name: str
    message: str


class ImportJobResponse(BaseModel):
    id: int
    dataset: ImportDataset
    status: ImportJobStatus
    filename: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    preview_rows: list[dict]
    errors: list[RowError]
    committed_at: datetime | None


class CommitResponse(BaseModel):
    id: int
    status: ImportJobStatus
    applied_rows: int
