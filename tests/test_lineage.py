"""
Testes unitários para src/etl/lineage.py (UCM-24).

Estratégia: todos os testes rodam sem backend Marquez e sem
openlineage-python instalado — testamos o comportamento de
degradação graciosa e a interface pública do LineageClient.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch, call

import pytest

import src.etl.lineage as lineage_module
from src.etl.lineage import (
    LineageClient,
    RAW_CARS_DATASET,
    CLEAN_CARS_DATASET,
    MANUFACTURER_STATS_DATASET,
    MODEL_FILE_DATASET,
    _ol_enabled,
    _now_iso,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_client(job_name: str = "test_job") -> LineageClient:
    """Cria um cliente com _client=None (sem backend configurado)."""
    return LineageClient(job_name=job_name)


# ── _ol_enabled() ─────────────────────────────────────────────────────────────

class TestOlEnabled:
    def test_disabled_when_no_url(self, monkeypatch):
        monkeypatch.delenv("OPENLINEAGE_URL", raising=False)
        # Recarregar variável do módulo
        monkeypatch.setattr(lineage_module, "_DEFAULT_URL", "")
        assert _ol_enabled() is False

    def test_disabled_when_package_unavailable(self, monkeypatch):
        monkeypatch.setattr(lineage_module, "_OL_AVAILABLE", False)
        monkeypatch.setattr(lineage_module, "_DEFAULT_URL", "http://marquez:5000")
        assert _ol_enabled() is False

    def test_enabled_when_url_and_package(self, monkeypatch):
        monkeypatch.setattr(lineage_module, "_OL_AVAILABLE", True)
        monkeypatch.setattr(lineage_module, "_DEFAULT_URL", "http://marquez:5000")
        assert _ol_enabled() is True


# ── _now_iso() ────────────────────────────────────────────────────────────────

class TestNowIso:
    def test_returns_iso_string(self):
        ts = _now_iso()
        assert isinstance(ts, str)
        assert "T" in ts  # ISO 8601 format
        assert "+" in ts or "Z" in ts or ts.endswith("+00:00")


# ── LineageClient — sem backend ───────────────────────────────────────────────

class TestLineageClientNoBackend:
    """Verifica comportamento quando OpenLineage não está configurado."""

    def test_client_created_without_errors(self):
        client = _make_client()
        assert client is not None
        assert client._client is None

    def test_start_returns_uuid_string(self):
        client = _make_client()
        run_id = client.start()
        assert isinstance(run_id, str)
        assert len(run_id) == 36  # UUID format

    def test_start_stores_run_id(self):
        client = _make_client()
        run_id = client.start()
        assert client._run_id == run_id

    def test_start_with_inputs_outputs_no_error(self):
        client = _make_client()
        run_id = client.start(
            inputs=[RAW_CARS_DATASET],
            outputs=[CLEAN_CARS_DATASET],
        )
        assert run_id is not None

    def test_complete_without_run_id_logs_warning(self, caplog):
        import logging
        client = _make_client()
        with caplog.at_level(logging.WARNING):
            client.complete()  # sem start() antes
        assert "run_id" in caplog.text

    def test_complete_after_start_no_error(self):
        client = _make_client()
        run_id = client.start()
        client.complete(run_id)  # não deve levantar exceção

    def test_fail_without_run_id_logs_warning(self, caplog):
        import logging
        client = _make_client()
        with caplog.at_level(logging.WARNING):
            client.fail()
        assert "run_id" in caplog.text

    def test_fail_after_start_no_error(self):
        client = _make_client()
        run_id = client.start()
        client.fail(run_id, error="test error")  # não deve levantar exceção

    def test_explicit_run_id_respected(self):
        client = _make_client()
        custom_id = "12345678-1234-1234-1234-123456789012"
        run_id = client.start(run_id=custom_id)
        assert run_id == custom_id

    def test_different_runs_have_unique_ids(self):
        client = _make_client()
        id1 = client.start()
        id2 = client.start()
        assert id1 != id2


# ── LineageClient — context manager ───────────────────────────────────────────

class TestLineageClientContextManager:
    def test_track_yields_run_id(self):
        client = _make_client()
        with client.track() as run_id:
            assert isinstance(run_id, str)
            assert len(run_id) == 36

    def test_track_calls_complete_on_success(self):
        client = _make_client()
        client.complete = MagicMock()
        with client.track():
            pass
        client.complete.assert_called_once()

    def test_track_calls_fail_on_exception(self):
        client = _make_client()
        client.fail = MagicMock()
        with pytest.raises(ValueError):
            with client.track():
                raise ValueError("test error")
        client.fail.assert_called_once()
        call_args = client.fail.call_args
        assert "test error" in str(call_args)

    def test_track_reraises_exception(self):
        client = _make_client()
        with pytest.raises(RuntimeError, match="re-raised"):
            with client.track():
                raise RuntimeError("re-raised")


# ── LineageClient — com backend mockado ───────────────────────────────────────

class TestLineageClientWithMockedBackend:
    """Verifica que os métodos corretos do OL client são chamados."""

    def test_is_ready_false_without_package(self, monkeypatch):
        """_is_ready() deve retornar False quando pacote não está instalado."""
        monkeypatch.setattr(lineage_module, "_OL_AVAILABLE", False)
        client = LineageClient(job_name="test_ready")
        client._client = MagicMock()  # simula client configurado
        assert client._is_ready() is False

    def test_is_ready_false_without_client(self, monkeypatch):
        """_is_ready() deve retornar False quando _client é None."""
        monkeypatch.setattr(lineage_module, "_OL_AVAILABLE", True)
        client = LineageClient(job_name="test_ready")
        # _client é None (sem URL configurada)
        assert client._is_ready() is False

    def test_is_ready_true_with_both(self, monkeypatch):
        """_is_ready() deve retornar True quando pacote + cliente disponíveis."""
        monkeypatch.setattr(lineage_module, "_OL_AVAILABLE", True)
        client = LineageClient(job_name="test_ready")
        client._client = MagicMock()
        assert client._is_ready() is True

    def test_start_noop_when_not_ready(self, monkeypatch):
        """start() deve retornar UUID mesmo sem backend, sem chamar _emit."""
        monkeypatch.setattr(lineage_module, "_OL_AVAILABLE", False)
        client = LineageClient(job_name="test_noop")
        client._client = MagicMock()  # would normally trigger emit
        run_id = client.start()
        # _emit não deve ser chamado (não está ready)
        client._client.emit.assert_not_called()
        assert len(run_id) == 36

    def test_emit_called_with_openlineage_available(self, monkeypatch):
        """Com OpenLineage disponível, _emit deve chamar client.emit()."""
        monkeypatch.setattr(lineage_module, "_OL_AVAILABLE", True)

        client = LineageClient(job_name="test_emit")
        mock_ol = MagicMock()
        client._client = mock_ol

        mock_event = MagicMock()
        client._emit(mock_event)

        mock_ol.emit.assert_called_once_with(mock_event)


# ── Datasets constantes ───────────────────────────────────────────────────────

class TestDatasetConstants:
    def test_raw_cars_dataset_has_required_keys(self):
        assert "name" in RAW_CARS_DATASET
        assert "namespace" in RAW_CARS_DATASET
        assert "fields" in RAW_CARS_DATASET
        assert len(RAW_CARS_DATASET["fields"]) > 0

    def test_clean_cars_dataset_namespace_is_postgres(self):
        assert "postgres" in CLEAN_CARS_DATASET["namespace"]

    def test_model_file_dataset_has_metric_fields(self):
        field_names = [f["name"] for f in MODEL_FILE_DATASET["fields"]]
        assert "r2_score" in field_names
        assert "rmse" in field_names

    def test_all_datasets_have_name_and_namespace(self):
        for ds in [RAW_CARS_DATASET, CLEAN_CARS_DATASET, MANUFACTURER_STATS_DATASET, MODEL_FILE_DATASET]:
            assert "name" in ds, f"Dataset sem 'name': {ds}"
            assert "namespace" in ds, f"Dataset sem 'namespace': {ds}"

    def test_fields_have_name_and_type(self):
        for ds in [RAW_CARS_DATASET, CLEAN_CARS_DATASET, MODEL_FILE_DATASET]:
            for field in ds["fields"]:
                assert "name" in field, f"Field sem 'name': {field} em {ds['name']}"
                assert "type" in field, f"Field sem 'type': {field} em {ds['name']}"
