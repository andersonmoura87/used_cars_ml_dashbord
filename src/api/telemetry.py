"""
Observabilidade: OpenTelemetry traces + Prometheus metrics.

Modo de operação:
  - Prometheus metrics (/metrics): sempre ativo via prometheus-fastapi-instrumentator
  - OTEL traces: ativo quando OTEL_EXPORTER_OTLP_ENDPOINT está definido

Métricas customizadas de negócio:
  - api_predictions_total          — contador de predições por status
  - api_prediction_duration_seconds — histograma de latência de predição
  - api_model_info                  — gauge com versão do modelo em produção
  - api_drift_checks_total          — contador de verificações de drift
  - api_etl_runs_total              — contador de runs ETL por status

Uso:
    # Em main.py:
    from src.api.telemetry import setup_telemetry, instrument_app
    setup_telemetry()
    instrument_app(app)

    # Em qualquer router/service:
    from src.api.telemetry import record_prediction, record_drift_check
    record_prediction(latency_seconds=0.12, status="success")
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ── Prometheus client (sempre disponível via instrumentator) ──────────────────
try:
    from prometheus_client import Counter, Gauge, Histogram, Info
    _PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client não instalado — métricas customizadas desabilitadas")

# ── prometheus-fastapi-instrumentator ────────────────────────────────────────
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    _INSTRUMENTATOR_AVAILABLE = True
except ImportError:  # pragma: no cover
    _INSTRUMENTATOR_AVAILABLE = False
    logger.warning("prometheus-fastapi-instrumentator não instalado — /metrics indisponível")

# ── OpenTelemetry (opcional — ativo apenas se OTEL_EXPORTER_OTLP_ENDPOINT definido) ──
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
    _OTEL_CORE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _OTEL_CORE_AVAILABLE = False

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    _OTEL_FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _OTEL_FASTAPI_AVAILABLE = False

try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    _OTEL_EXPORTER_AVAILABLE = True
except ImportError:  # pragma: no cover
    _OTEL_EXPORTER_AVAILABLE = False

# ── Métricas customizadas ─────────────────────────────────────────────────────

# Usamos lazy initialization para não falhar ao importar se prometheus não estiver disponível
_predictions_counter:  Optional["Counter"]   = None
_prediction_histogram: Optional["Histogram"] = None
_model_info_gauge:     Optional["Gauge"]     = None
_drift_counter:        Optional["Counter"]   = None
_etl_counter:          Optional["Counter"]   = None
_model_info_label:     Optional["Info"]      = None


def _init_metrics() -> None:
    """
    Inicializa as métricas Prometheus customizadas (idempotente).

    Usa try/except para suportar reloads do módulo em testes sem falhar
    com 'Duplicated timeseries in CollectorRegistry'.
    """
    global _predictions_counter, _prediction_histogram, _model_info_gauge
    global _drift_counter, _etl_counter, _model_info_label

    if not _PROMETHEUS_AVAILABLE:
        return
    if _predictions_counter is not None:
        return  # já inicializado nesta instância do módulo

    try:
        _predictions_counter = Counter(
            "api_predictions_total",
            "Total de predições de preço realizadas",
            labelnames=["status", "model_version"],
        )
        _prediction_histogram = Histogram(
            "api_prediction_duration_seconds",
            "Latência das predições de preço em segundos",
            labelnames=["status"],
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
        )
        _model_info_gauge = Gauge(
            "api_model_version_info",
            "Versão atual do modelo em produção (1 = ativo, 0 = inativo)",
            labelnames=["model_name", "version", "stage"],
        )
        _drift_counter = Counter(
            "api_drift_checks_total",
            "Total de verificações de drift executadas",
            labelnames=["result"],  # "drift" | "no_drift" | "error"
        )
        _etl_counter = Counter(
            "api_etl_runs_total",
            "Total de runs do pipeline ETL",
            labelnames=["status"],  # "success" | "failure"
        )
        _model_info_label = Info(
            "api_model_build",
            "Informações do build/deploy atual",
        )
        logger.info("Métricas Prometheus customizadas inicializadas")
    except ValueError:
        # Métricas já registradas no CollectorRegistry global (ex: reload em testes).
        # Recupera as instâncias existentes do registry para manter funcionalidade.
        from prometheus_client import REGISTRY
        for collector in REGISTRY._names_to_collectors.values():
            name = getattr(collector, "_name", "")
            if name == "api_predictions":
                _predictions_counter = collector  # type: ignore[assignment]
            elif name == "api_prediction_duration":
                _prediction_histogram = collector  # type: ignore[assignment]
            elif name == "api_model_version":
                _model_info_gauge = collector  # type: ignore[assignment]
            elif name == "api_drift_checks":
                _drift_counter = collector  # type: ignore[assignment]
            elif name == "api_etl_runs":
                _etl_counter = collector  # type: ignore[assignment]
        logger.debug("Métricas Prometheus já registradas — reutilizando instâncias existentes")


# ── API pública para registrar eventos ───────────────────────────────────────

def record_prediction(
    latency_seconds: float,
    status: str = "success",
    model_version: str = "unknown",
) -> None:
    """
    Registra uma predição de preço.

    Args:
        latency_seconds: tempo de resposta da predição
        status: "success" | "error" | "cache_hit"
        model_version: versão do modelo usado (ex: "v3" ou hash)
    """
    if _predictions_counter is None:
        _init_metrics()
    if _predictions_counter:
        _predictions_counter.labels(status=status, model_version=model_version).inc()
    if _prediction_histogram:
        _prediction_histogram.labels(status=status).observe(latency_seconds)


def record_drift_check(result: str) -> None:
    """
    Registra o resultado de uma verificação de drift.

    Args:
        result: "drift" | "no_drift" | "error"
    """
    if _drift_counter is None:
        _init_metrics()
    if _drift_counter:
        _drift_counter.labels(result=result).inc()


def record_etl_run(status: str) -> None:
    """
    Registra o resultado de um run ETL.

    Args:
        status: "success" | "failure"
    """
    if _etl_counter is None:
        _init_metrics()
    if _etl_counter:
        _etl_counter.labels(status=status).inc()


def set_model_version(model_name: str, version: str, stage: str) -> None:
    """
    Atualiza o gauge de versão do modelo.

    Args:
        model_name: nome do modelo no registry
        version: versão (ex: "5")
        stage: "Production" | "Staging" | "None"
    """
    if _model_info_gauge is None:
        _init_metrics()
    if _model_info_gauge:
        _model_info_gauge.labels(
            model_name=model_name,
            version=version,
            stage=stage,
        ).set(1.0)


def set_build_info(version: str, environment: str, git_sha: str = "unknown") -> None:
    """
    Define metadados do build para identificação no Grafana.

    Args:
        version: versão da aplicação (ex: "0.2.0")
        environment: "development" | "staging" | "production"
        git_sha: hash do commit (opcional)
    """
    if _model_info_label is None:
        _init_metrics()
    if _model_info_label:
        _model_info_label.info({
            "version": version,
            "environment": environment,
            "git_sha": git_sha,
        })


# ── Setup principal ───────────────────────────────────────────────────────────

def setup_telemetry(
    service_name: str = "used-cars-ml-api",
    service_version: str = "0.2.0",
) -> None:
    """
    Inicializa:
      1. Métricas Prometheus customizadas
      2. OTEL traces (se OTEL_EXPORTER_OTLP_ENDPOINT estiver configurado)
    """
    _init_metrics()

    environment = os.getenv("ENVIRONMENT", "development")
    git_sha     = os.getenv("GIT_SHA", "unknown")
    set_build_info(service_version, environment, git_sha)

    # ── OpenTelemetry traces ──────────────────────────────────────────────────
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not otlp_endpoint:
        logger.info(
            "OTEL_EXPORTER_OTLP_ENDPOINT não configurado — traces OTEL desabilitados. "
            "Para habilitar: OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317"
        )
        return

    if not _OTEL_CORE_AVAILABLE:
        logger.warning("opentelemetry-sdk não instalado — traces OTEL indisponível mesmo com endpoint configurado")
        return

    if not _OTEL_EXPORTER_AVAILABLE:
        logger.warning("opentelemetry-exporter-otlp não instalado — traces não exportados")
        return

    resource = Resource.create({
        SERVICE_NAME:    service_name,
        SERVICE_VERSION: service_version,
        "deployment.environment": environment,
    })
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    logger.info(
        "OpenTelemetry traces habilitados — serviço: %s  endpoint: %s",
        service_name, otlp_endpoint,
    )


def instrument_app(app: object) -> None:
    """
    Instrumenta o app FastAPI:
      1. /metrics (Prometheus via prometheus-fastapi-instrumentator)
      2. Auto-tracing de rotas OTEL (se configurado)

    Args:
        app: instância do FastAPI
    """
    if _INSTRUMENTATOR_AVAILABLE:
        instrumentator = Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            should_instrument_requests_inprogress=True,
            excluded_handlers=["/metrics", "/health"],
            inprogress_name="api_http_requests_inprogress",
            inprogress_labels=True,
        )
        instrumentator.instrument(app).expose(app, include_in_schema=False, tags=["system"])
        logger.info("prometheus-fastapi-instrumentator ativo — endpoint: /metrics")
    else:
        logger.warning("prometheus-fastapi-instrumentator não disponível — /metrics não exposto")

    if _OTEL_FASTAPI_AVAILABLE and os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI OTEL auto-instrumentation ativo")
