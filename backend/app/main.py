"""FastAPI application entry point."""

from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.middleware.request_context import RequestContextMiddleware

settings = get_settings()
configure_logging(settings)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Initial API foundation for the Journal Reviewer Simulator. "
        "Scientific review functionality is not implemented in this release."
    ),
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
