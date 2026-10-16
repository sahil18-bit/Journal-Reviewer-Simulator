"""Consistent API error response tests."""

import pytest
from fastapi import FastAPI, Query
from fastapi.testclient import TestClient

from app.core.errors import error_payload, register_exception_handlers
from app.middleware.request_context import RequestContextMiddleware

pytestmark = pytest.mark.api


def test_error_payload_has_stable_envelope() -> None:
    result = error_payload(
        code="example_error",
        message="Safe message",
        request_id="req-123",
    )

    assert result == {
        "error": {
            "code": "example_error",
            "message": "Safe message",
            "request_id": "req-123",
            "details": [],
        }
    }


def test_unknown_route_returns_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/not-a-route")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "http_404"
    assert body["error"]["request_id"] == response.headers["x-request-id"]
    assert "not found" in body["error"]["message"].lower()


def test_validation_error_is_sanitized() -> None:
    test_app = FastAPI()
    test_app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(test_app)

    @test_app.get("/example")
    async def example(name: str = Query(min_length=3)) -> dict[str, str]:
        return {"name": name}

    with TestClient(test_app) as test_client:
        response = test_client.get("/example", params={"name": "x"})

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "request_validation_error"
    assert body["error"]["request_id"] == response.headers["x-request-id"]
    assert body["error"]["details"]
    assert "input" not in body["error"]["details"][0]


def test_unexpected_error_message_does_not_leak_details() -> None:
    test_app = FastAPI()
    test_app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(test_app)

    @test_app.get("/explode")
    async def explode() -> None:
        raise RuntimeError("sensitive manuscript text")

    with TestClient(test_app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/explode")

    assert response.status_code == 500
    assert response.json()["error"]["message"] == "An unexpected error occurred."
    assert "sensitive manuscript text" not in response.text
