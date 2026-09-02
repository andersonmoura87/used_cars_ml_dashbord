"""Readiness da camada canônica contra PostgreSQL real."""

import pytest

from src.database import connection
from tests.integration.test_etl_postgresql import _require_integration


pytestmark = pytest.mark.integration


def test_readiness_with_real_postgresql():
    _require_integration()
    connection._engine = None
    connection._SessionFactory = None
    try:
        assert connection.check_database_readiness() is True
    finally:
        if connection._engine is not None:
            connection._engine.dispose()
        connection._engine = None
        connection._SessionFactory = None
