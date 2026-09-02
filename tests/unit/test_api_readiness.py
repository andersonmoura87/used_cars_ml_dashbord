"""Liveness, readiness e fail-fast da configuração da API."""

import asyncio
from unittest.mock import patch

from fastapi.responses import JSONResponse

from src.api import database
from src.api import main
from src.database.connection import DatabaseConfigurationError


def test_liveness_does_not_access_database():
    with patch.object(main, "check_database_readiness") as readiness:
        response = asyncio.run(main.health_check())

    assert response["status"] == "healthy"
    readiness.assert_not_called()


def test_readiness_returns_ready_when_database_is_available():
    with patch.object(main, "check_database_readiness", return_value=True):
        response = asyncio.run(main.readiness_check())

    assert response == {"status": "ready", "database": "available"}


def test_readiness_returns_sanitized_503_when_database_is_unavailable():
    secret = "do-not-return-this-password"
    with patch.object(
        main,
        "check_database_readiness",
        side_effect=RuntimeError(secret),
    ):
        response = asyncio.run(main.readiness_check())

    assert isinstance(response, JSONResponse)
    assert response.status_code == 503
    assert secret.encode() not in response.body
    assert b"not_ready" in response.body


def test_production_startup_validates_configuration():
    with patch.object(main, "_IS_PROD_LIKE", True), patch.object(
        main, "_ENVIRONMENT", "production"
    ), patch.object(
        main,
        "validate_database_config",
        side_effect=DatabaseConfigurationError("DB_PASSWORD"),
    ) as validate:
        try:
            asyncio.run(main.validate_startup_database_configuration())
        except DatabaseConfigurationError:
            pass
        else:
            raise AssertionError("startup deveria falhar com configuração inválida")

    validate.assert_called_once_with("production")


def test_development_startup_does_not_force_database_connection():
    with patch.object(main, "_IS_PROD_LIKE", False), patch.object(
        main,
        "validate_database_config",
    ) as validate:
        asyncio.run(main.validate_startup_database_configuration())

    validate.assert_not_called()


def test_get_db_preserves_session_yield_and_close_contract():
    session = type("Session", (), {"close": lambda self: setattr(self, "closed", True)})()
    session.closed = False
    with patch.object(database, "get_db_session", return_value=session):
        dependency = database.get_db()
        assert next(dependency) is session
        dependency.close()

    assert session.closed is True
