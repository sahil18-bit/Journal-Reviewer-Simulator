"""Health endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="API liveness check")
async def health_check() -> dict[str, str]:
    """Return API liveness only; this does not verify external dependencies."""
    return {"status": "ok"}
