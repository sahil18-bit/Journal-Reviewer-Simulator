"""Configuration validation tests."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.unit
def test_defaults_are_safe_for_local_development() -> None:
    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.log_level == "INFO"
    assert settings.api_prefix == "/api/v1"
    assert "localhost" in settings.allowed_hosts


@pytest.mark.unit
def test_allowed_hosts_parse_comma_separated_value() -> None:
    settings = Settings(_env_file=None, allowed_hosts="localhost,example.test")

    assert settings.allowed_hosts == ["localhost", "example.test"]


@pytest.mark.unit
@pytest.mark.parametrize("prefix", ["api/v1", "/", "/api/v1/", "/api//v1", "/api v1"])
def test_invalid_api_prefix_is_rejected(prefix: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, api_prefix=prefix)


@pytest.mark.unit
def test_empty_allowed_hosts_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, allowed_hosts=[])
