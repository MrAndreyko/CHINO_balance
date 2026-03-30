from fastapi import APIRouter

router = APIRouter()


@router.get("/health", summary="Service health check")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
