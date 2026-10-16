"""Health endpoint tests."""

import re

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.api


def test_health_endpoint_returns_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert re.fullmatch(r"[A-Za-z0-9._-]{1,64}", response.headers["x-request-id"])


def test_valid_request_id_is_preserved(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "test-request_123"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "test-request_123"


def test_invalid_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "not safe\\nvalue"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] != "not safe\\nvalue"
    assert re.fullmatch(r"[A-Za-z0-9._-]{1,64}", response.headers["x-request-id"])
