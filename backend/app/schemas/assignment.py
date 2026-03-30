from datetime import datetime

from pydantic import BaseModel


class AssignmentRunRequest(BaseModel):
    run_type: str
    triggered_by: str = "api"


class AssignmentRunResponse(BaseModel):
    run_id: int
    run_type: str
    run_status: str
    metadata: dict | None
    created_at: datetime
