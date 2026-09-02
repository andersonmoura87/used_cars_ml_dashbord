"""Controle de opt-in e falhas da integração PostgreSQL."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from tests.integration import test_etl_postgresql as integration


@pytest.mark.parametrize("value", [None, "", "0", "false", "FALSE", "off"])
def test_integration_disabled_is_skipped(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("INTEGRATION_DB", raising=False)
    else:
        monkeypatch.setenv("INTEGRATION_DB", value)

    with pytest.raises(pytest.skip.Exception):
        integration._require_integration()


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "YeS", "on", "ON"])
def test_enabled_values_request_integration(monkeypatch, value):
    monkeypatch.setenv("INTEGRATION_DB", value)
    integration._require_integration()


def test_requested_integration_connection_error_fails_without_secret(monkeypatch):
    monkeypatch.setenv("INTEGRATION_DB", "1")
    monkeypatch.setenv("TEST_DB_PASSWORD", "never-show-this-password")
    engine = MagicMock()
    engine.begin.side_effect = OperationalError("connect", {}, Exception("authentication"))

    integration._require_integration()
    with patch.object(integration, "create_engine", return_value=engine):
        with pytest.raises(pytest.fail.Exception) as failure:
            integration._setup_postgres_sessions()

    message = str(failure.value)
    assert "PostgreSQL integration requested but database is unavailable" in message
    assert "never-show-this-password" not in message


def test_requested_integration_valid_setup_returns_session_factory(monkeypatch):
    monkeypatch.setenv("INTEGRATION_DB", "true")
    monkeypatch.setenv("TEST_DB_PASSWORD", "test-password")
    admin_engine = MagicMock()
    data_engine = MagicMock()
    expected_factory = MagicMock()

    integration._require_integration()
    with patch.object(
        integration, "create_engine", side_effect=[admin_engine, data_engine]
    ), patch.object(integration.Base.metadata, "create_all") as create_all, patch.object(
        integration, "sessionmaker", return_value=expected_factory
    ):
        factory, engine, admin, schema = integration._setup_postgres_sessions()

    assert factory is expected_factory
    assert engine is data_engine
    assert admin is admin_engine
    assert schema.startswith("etl_integration_")
    create_all.assert_called_once_with(data_engine)
