from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.import_job import ImportDataset, ImportJobStatus
from app.schemas.imports import CommitResponse, ImportJobResponse, RowError
from app.services.import_pipeline import (
    commit_job,
    create_preview_job,
    get_job_errors,
    get_job_or_404,
    parse_file,
)

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/{dataset}/preview", response_model=ImportJobResponse)
def preview_import(dataset: ImportDataset, file: UploadFile = File(...), db: Session = Depends(get_db)) -> ImportJobResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must include a filename")

    rows = parse_file(file.filename, file.file.read())
    job = create_preview_job(dataset=dataset, filename=file.filename, rows=rows, db=db)
    errors = get_job_errors(job.id, db)

    return ImportJobResponse(
        id=job.id,
        dataset=job.dataset,
        status=job.status,
        filename=job.filename,
        total_rows=job.total_rows,
        valid_rows=job.valid_rows,
        invalid_rows=job.invalid_rows,
        preview_rows=job.preview_rows_json,
        errors=[RowError(row_number=e.row_number, column_name=e.column_name, message=e.message) for e in errors],
        committed_at=job.committed_at,
    )


@router.post("/{job_id}/commit", response_model=CommitResponse)
def commit_import(job_id: int, db: Session = Depends(get_db)) -> CommitResponse:
    job = get_job_or_404(job_id, db)
    applied_rows = commit_job(job, db)
    return CommitResponse(id=job.id, status=ImportJobStatus.COMMITTED, applied_rows=applied_rows)


@router.get("/{job_id}", response_model=ImportJobResponse)
def get_import_job(job_id: int, db: Session = Depends(get_db)) -> ImportJobResponse:
    job = get_job_or_404(job_id, db)
    errors = get_job_errors(job.id, db)
    return ImportJobResponse(
        id=job.id,
        dataset=job.dataset,
        status=job.status,
        filename=job.filename,
        total_rows=job.total_rows,
        valid_rows=job.valid_rows,
        invalid_rows=job.invalid_rows,
        preview_rows=job.preview_rows_json,
        errors=[RowError(row_number=e.row_number, column_name=e.column_name, message=e.message) for e in errors],
        committed_at=job.committed_at,
    )
