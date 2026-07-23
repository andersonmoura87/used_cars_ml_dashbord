"""
Testes unitários — src.database.connection (UCM-29).

Substitui o antigo test_database skipped (exigia DB populado com ETL legado).
Integração opcional: INTEGRATION_DB=1 + DB_* no ambiente.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.database import connection as conn_mod


@pytest.fixture(autouse=True)
def _reset_session_singleton():
    """Evita vazamento de engine entre testes."""
    conn_mod._engine = None
    conn_mod._SessionFactory = None
    yield
    conn_mod._engine = None
    conn_mod._SessionFactory = None


class TestGetDatabaseUrl:
    def test_builds_url(self, monkeypatch):
        monkeypatch.setenv("DB_USER", "u")
        monkeypatch.setenv("DB_PASSWORD", "p")
        monkeypatch.setenv("DB_HOST", "db.local")
        monkeypatch.setenv("DB_PORT", "5433")
        monkeypatch.setenv("DB_NAME", "cars")
        assert conn_mod.get_database_url() == "postgresql://u:p@db.local:5433/cars"

    def test_defaults_host_port_name(self, monkeypatch):
        monkeypatch.setenv("DB_USER", "u")
        monkeypatch.setenv("DB_PASSWORD", "secret")
        monkeypatch.delenv("DB_HOST", raising=False)
        monkeypatch.delenv("DB_PORT", raising=False)
        monkeypatch.delenv("DB_NAME", raising=False)
        url = conn_mod.get_database_url()
        assert "localhost" in url
        assert ":5432/" in url
        assert url.endswith("/used_cars")

    def test_missing_password_raises(self, monkeypatch):
        monkeypatch.setenv("DB_USER", "u")
        monkeypatch.delenv("DB_PASSWORD", raising=False)
        with pytest.raises(KeyError):
            conn_mod.get_database_url()


class TestCreateDbEngine:
    def test_success(self, monkeypatch):
        monkeypatch.setenv("DB_USER", "u")
        monkeypatch.setenv("DB_PASSWORD", "p")
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = lambda s: mock_conn
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.database.connection.create_engine", return_value=mock_engine) as ce:
            engine = conn_mod.create_db_engine()

        assert engine is mock_engine
        ce.assert_called_once()
        mock_conn.execute.assert_called_once()

    def test_sqlalchemy_error_propagates(self, monkeypatch):
        monkeypatch.setenv("DB_USER", "u")
        monkeypatch.setenv("DB_PASSWORD", "p")
        with patch(
            "src.database.connection.create_engine",
            side_effect=SQLAlchemyError("boom"),
        ):
            with pytest.raises(SQLAlchemyError):
                conn_mod.create_db_engine()


class TestTestConnection:
    def test_returns_true_on_success(self, monkeypatch):
        monkeypatch.setenv("DB_USER", "u")
        monkeypatch.setenv("DB_PASSWORD", "p")
        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_conn.execute.return_value.scalar.return_value = "PostgreSQL 15"
        mock_engine.connect.return_value.__enter__ = lambda s: mock_conn
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.database.connection.create_db_engine", return_value=mock_engine):
            # create_db_engine is called inside test_connection — also need SELECT 1 path
            assert conn_mod.test_connection() is True

    def test_returns_false_on_error(self, monkeypatch):
        monkeypatch.setenv("DB_USER", "u")
        monkeypatch.setenv("DB_PASSWORD", "p")
        with patch(
            "src.database.connection.create_db_engine",
            side_effect=SQLAlchemyError("down"),
        ):
            assert conn_mod.test_connection() is False


class TestGetDbSession:
    def test_session_factory_singleton(self, monkeypatch):
        monkeypatch.setenv("DB_USER", "u")
        monkeypatch.setenv("DB_PASSWORD", "p")
        mock_engine = MagicMock()
        mock_factory = MagicMock(return_value=MagicMock())

        with patch("src.database.connection.create_db_engine", return_value=mock_engine), \
             patch("src.database.connection.sessionmaker", return_value=mock_factory) as sm:
            s1 = conn_mod.get_db_session()
            s2 = conn_mod.get_db_session()

        sm.assert_called_once()
        assert mock_factory.call_count == 2
        assert s1 is not None and s2 is not None


@pytest.mark.integration
def test_live_database_connection():
    """
    Integração opcional — só roda com INTEGRATION_DB=1 e DB_* configurados.

    Não exige tabelas populadas (só SELECT 1 / version).
    """
    if os.getenv("INTEGRATION_DB", "").lower() not in ("1", "true", "yes"):
        pytest.skip("Defina INTEGRATION_DB=1 para rodar contra PostgreSQL real")

    if not os.getenv("DB_PASSWORD"):
        pytest.skip("DB_PASSWORD não definido")

    # Reset singleton para usar env real
    conn_mod._engine = None
    conn_mod._SessionFactory = None
    assert conn_mod.test_connection() is True
