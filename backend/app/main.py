"""FastAPI application entry point."""

if __name__ == "__main__":  # Clicking "Run" on this file starts the whole app (see run.py)
    import runpy
    from pathlib import Path

    runpy.run_path(str(Path(__file__).resolve().parents[2] / "run.py"), run_name="__main__")
    raise SystemExit(0)

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.review import router as review_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.middleware.request_context import RequestContextMiddleware

settings = get_settings()
configure_logging(settings)
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="An AI peer-review pipeline built from prompt patterns.",
    # Keep debug tracebacks out of HTTP responses in every environment.
    debug=False,
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_hosts,
)
app.add_middleware(RequestContextMiddleware)
register_exception_handlers(app)
app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(review_router, prefix=settings.api_prefix)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
