"""Shared test fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Return a test client for the API application."""
    with TestClient(app) as test_client:
        yield test_client
