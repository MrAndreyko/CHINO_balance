from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.assignment_run import AssignmentRun
from app.schemas.assignment import AssignmentRunRequest, AssignmentRunResponse
from app.services.assignment_engine import run_assignment_engine

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.post("/run", response_model=AssignmentRunResponse)
def run_assignment(payload: AssignmentRunRequest, db: Session = Depends(get_db)) -> AssignmentRunResponse:
    try:
        run = run_assignment_engine(db=db, run_type=payload.run_type, triggered_by=payload.triggered_by)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return AssignmentRunResponse(
        run_id=run.id,
        run_type=run.run_type,
        run_status=run.run_status,
        metadata=run.metadata_json,
        created_at=run.created_at,
    )


@router.get("/{run_id}", response_model=AssignmentRunResponse)
def get_assignment_run(run_id: int, db: Session = Depends(get_db)) -> AssignmentRunResponse:
    run = db.scalar(select(AssignmentRun).where(AssignmentRun.id == run_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Assignment run not found")

    return AssignmentRunResponse(
        run_id=run.id,
        run_type=run.run_type,
        run_status=run.run_status,
        metadata=run.metadata_json,
        created_at=run.created_at,
    )
