"""Request ID and request-completion logging middleware."""

import logging
import re
import time
import uuid
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import log_event

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestContextMiddleware:
    """Attach a safe request ID and log request completion without logging payloads."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        supplied_id = headers.get(b"x-request-id", b"").decode("ascii", errors="ignore")
        request_id = (
            supplied_id if _REQUEST_ID_PATTERN.fullmatch(supplied_id) else str(uuid.uuid4())
        )
        scope.setdefault("state", {})["request_id"] = request_id
        start = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                response_headers = list(message.get("headers", []))
                response_headers = [
                    (key, value)
                    for key, value in response_headers
                    if key.lower() != b"x-request-id"
                ]
                response_headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = response_headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            log_event(
                logging.ERROR,
                "request_failed",
                request_id=request_id,
                method=scope.get("method"),
                path=scope.get("path"),
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            log_event(
                logging.INFO,
                "request_completed",
                request_id=request_id,
                method=scope.get("method"),
                path=scope.get("path"),
                status_code=status_code,
                duration_ms=duration_ms,
            )
