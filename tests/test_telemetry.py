"""
Testes unitários para src/api/telemetry.py (UCM-22).

Estratégia: todos os testes rodam sem prometheus_client instalado.
Os testes de métricas verificam o comportamento do módulo
quando as dependências estão disponíveis (mocked).
"""
from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock, patch


# ── Helpers ───────────────────────────────────────────────────────────────────

def _reload_telemetry():
    """Faz reload do módulo para resetar estado global entre testes."""
    if "src.api.telemetry" in sys.modules:
        del sys.modules["src.api.telemetry"]
    import src.api.telemetry as tel
    return tel


# ── Testes: estado inicial do módulo ─────────────────────────────────────────

class TestModuleImport:
    def test_module_importable(self):
        """Módulo deve importar sem erros mesmo sem dependências opcionais."""
        import src.api.telemetry as tel
        assert tel is not None

    def test_public_api_exported(self):
        """Funções públicas devem existir no módulo."""
        import src.api.telemetry as tel
        assert callable(tel.setup_telemetry)
        assert callable(tel.instrument_app)
        assert callable(tel.record_prediction)
        assert callable(tel.record_drift_check)
        assert callable(tel.record_etl_run)
        assert callable(tel.set_model_version)
        assert callable(tel.set_build_info)


# ── Testes: record_* sem prometheus ──────────────────────────────────────────

class TestRecordFunctionsNoop:
    """record_* devem ser no-ops quando prometheus_client não está disponível."""

    def test_record_prediction_noop(self):
        tel = _reload_telemetry()
        tel._PROMETHEUS_AVAILABLE = False
        tel._predictions_counter = None
        tel._prediction_histogram = None
        # não deve levantar exceção
        tel.record_prediction(latency_seconds=0.1, status="success", model_version="v1")

    def test_record_drift_noop(self):
        tel = _reload_telemetry()
        tel._PROMETHEUS_AVAILABLE = False
        tel._drift_counter = None
        tel.record_drift_check(result="no_drift")

    def test_record_etl_noop(self):
        tel = _reload_telemetry()
        tel._PROMETHEUS_AVAILABLE = False
        tel._etl_counter = None
        tel.record_etl_run(status="success")

    def test_set_model_version_noop(self):
        tel = _reload_telemetry()
        tel._PROMETHEUS_AVAILABLE = False
        tel._model_info_gauge = None
        tel.set_model_version(model_name="used_cars", version="5", stage="Production")

    def test_set_build_info_noop(self):
        tel = _reload_telemetry()
        tel._PROMETHEUS_AVAILABLE = False
        tel._model_info_label = None
        tel.set_build_info(version="1.0.0", environment="test")


# ── Testes: record_* COM métricas mockadas ────────────────────────────────────

class TestRecordFunctionsWithMocks:
    """Verifica que record_* chamam os métodos corretos nas métricas Prometheus."""

    def _make_counter(self):
        """Cria um mock de Counter com labels()."""
        m = MagicMock()
        m.labels.return_value = m
        return m

    def _make_histogram(self):
        m = MagicMock()
        m.labels.return_value = m
        return m

    def _make_gauge(self):
        m = MagicMock()
        m.labels.return_value = m
        return m

    def _make_info(self):
        return MagicMock()

    def test_record_prediction_calls_counter_and_histogram(self):
        tel = _reload_telemetry()
        counter   = self._make_counter()
        histogram = self._make_histogram()
        tel._predictions_counter  = counter
        tel._prediction_histogram = histogram

        tel.record_prediction(latency_seconds=0.25, status="success", model_version="v3")

        counter.labels.assert_called_once_with(status="success", model_version="v3")
        counter.inc.assert_called_once()
        histogram.labels.assert_called_once_with(status="success")
        histogram.observe.assert_called_once_with(0.25)

    def test_record_prediction_default_args(self):
        tel = _reload_telemetry()
        counter   = self._make_counter()
        histogram = self._make_histogram()
        tel._predictions_counter  = counter
        tel._prediction_histogram = histogram

        tel.record_prediction(latency_seconds=0.05)

        counter.labels.assert_called_once_with(status="success", model_version="unknown")

    def test_record_drift_check_labels(self):
        tel = _reload_telemetry()
        counter = self._make_counter()
        tel._drift_counter = counter

        tel.record_drift_check("drift")

        counter.labels.assert_called_once_with(result="drift")
        counter.inc.assert_called_once()

    def test_record_etl_run_labels(self):
        tel = _reload_telemetry()
        counter = self._make_counter()
        tel._etl_counter = counter

        tel.record_etl_run("failure")

        counter.labels.assert_called_once_with(status="failure")
        counter.inc.assert_called_once()

    def test_set_model_version_gauge(self):
        tel = _reload_telemetry()
        gauge = self._make_gauge()
        tel._model_info_gauge = gauge

        tel.set_model_version("used_cars_price_model", "5", "Production")

        gauge.labels.assert_called_once_with(
            model_name="used_cars_price_model",
            version="5",
            stage="Production",
        )
        gauge.set.assert_called_once_with(1.0)

    def test_set_build_info_info(self):
        tel = _reload_telemetry()
        info = self._make_info()
        tel._model_info_label = info

        tel.set_build_info("1.0.0", "staging", "abc123")

        info.info.assert_called_once_with({
            "version": "1.0.0",
            "environment": "staging",
            "git_sha": "abc123",
        })


# ── Testes: setup_telemetry ───────────────────────────────────────────────────

class TestSetupTelemetry:
    def test_setup_without_otlp_endpoint(self, monkeypatch):
        """Deve completar sem erros quando OTLP_ENDPOINT não está definido."""
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        tel = _reload_telemetry()
        tel.setup_telemetry()  # não deve levantar exceção

    def test_setup_with_otlp_but_no_otel_installed(self, monkeypatch):
        """Com endpoint configurado mas OTEL não instalado, deve logar warning sem falhar."""
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://fake:4317")
        tel = _reload_telemetry()
        tel._OTEL_CORE_AVAILABLE = False
        tel.setup_telemetry()  # não deve levantar exceção


# ── Testes: instrument_app ────────────────────────────────────────────────────

class TestInstrumentApp:
    def test_instrument_app_without_instrumentator(self):
        """Deve ser no-op quando instrumentator não disponível."""
        tel = _reload_telemetry()
        tel._INSTRUMENTATOR_AVAILABLE = False
        mock_app = MagicMock()
        tel.instrument_app(mock_app)  # não deve levantar exceção

    def test_instrument_app_with_instrumentator(self, monkeypatch):
        """Deve chamar instrumentator.instrument().expose() quando disponível."""
        tel = _reload_telemetry()

        mock_inst_instance = MagicMock()
        mock_inst_instance.instrument.return_value = mock_inst_instance
        mock_inst_instance.expose.return_value = mock_inst_instance

        mock_instrumentator_class = MagicMock(return_value=mock_inst_instance)
        monkeypatch.setattr(tel, "_INSTRUMENTATOR_AVAILABLE", True)
        monkeypatch.setattr(tel, "Instrumentator", mock_instrumentator_class, raising=False)

        mock_app = MagicMock()

        # Injetar o mock diretamente no namespace do módulo
        import src.api.telemetry as real_tel

        original = getattr(real_tel, "Instrumentator", None)
        try:
            real_tel.Instrumentator = mock_instrumentator_class  # type: ignore[attr-defined]
            real_tel._INSTRUMENTATOR_AVAILABLE = True
            real_tel.instrument_app(mock_app)
            mock_inst_instance.instrument.assert_called_once_with(mock_app)
        finally:
            if original is not None:
                real_tel.Instrumentator = original  # type: ignore[attr-defined]
            real_tel._INSTRUMENTATOR_AVAILABLE = tel._INSTRUMENTATOR_AVAILABLE
