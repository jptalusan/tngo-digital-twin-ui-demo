from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Health check",
    description="Basic liveness check for the API service.",
)
def health() -> dict:
    return {"status": "ok"}
