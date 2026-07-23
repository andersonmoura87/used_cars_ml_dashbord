"""
UCM-27 — testes do stub Prefect / legado alinhados ao canônico.

Os testes antigos de DataCleaner / DataMonitor / PostgresLoader foram
removidos (paths deprecados). Cobertura do canônico está em:
  tests/unit/test_extract.py
  tests/unit/test_transform.py
  tests/unit/test_load.py
  tests/unit/test_run_pipeline.py
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


def test_cars_etl_stub_delegates_to_run_pipeline():
    """cars_etl_pipeline deve apenas chamar o pipeline canônico."""
    with patch("src.etl.run_pipeline.run_pipeline", return_value=True) as mock_run:
        with pytest.warns(DeprecationWarning, match="DEPRECATED"):
            from scripts.pipeline.cars_etl import cars_etl_pipeline
            assert cars_etl_pipeline() is True
        mock_run.assert_called_once()


def test_cars_etl_stub_propagates_failure():
    import scripts.pipeline.cars_etl as mod

    with patch("src.etl.run_pipeline.run_pipeline", return_value=False):
        assert mod.cars_etl_pipeline() is False
