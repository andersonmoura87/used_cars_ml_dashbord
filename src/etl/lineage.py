"""
Data Lineage via OpenLineage (UCM-24).

Captura e emite eventos de linhagem de dados para um backend compatível
com OpenLineage (Marquez, Atlan, DataHub, etc.).

Modo de operação:
  - Ativo quando OPENLINEAGE_URL estiver configurado
  - Degradação graciosa: sem a variável ou sem o pacote, não há efeito

Padrão de uso:
    from src.etl.lineage import LineageClient

    client = LineageClient(job_name="etl_run_pipeline", namespace="used_cars")
    run_id = client.start(inputs=[...], outputs=[...])
    try:
        ...  # lógica do pipeline
        client.complete(run_id, outputs=[...])
    except Exception as exc:
        client.fail(run_id, error=str(exc))
        raise

Ou via context manager:
    with LineageClient("etl_run_pipeline") as client:
        ...  # emit_start() e emit_complete()/emit_fail() automáticos

Datasets são descritos como dicionários:
    {"namespace": "postgres", "name": "cars", "fields": [{"name": "price", "type": "DOUBLE"}]}
"""
from __future__ import annotations

import logging
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator

logger = logging.getLogger(__name__)

# ── OpenLineage — importação opcional ─────────────────────────────────────────
try:
    from openlineage.client import OpenLineageClient
    from openlineage.client.run import (
        InputDataset,
        Job,
        OutputDataset,
        Run,
        RunEvent,
        RunState,
    )
    from openlineage.client.facet import (
        DocumentationJobFacet,
        SchemaDatasetFacet,
        SchemaField,
    )
    _OL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _OL_AVAILABLE = False
    logger.debug("openlineage-python não instalado — lineage desabilitado")


# ── Namespace e URL padrão ────────────────────────────────────────────────────

_DEFAULT_NAMESPACE = os.getenv("OPENLINEAGE_NAMESPACE", "used_cars_ml")
_DEFAULT_URL       = os.getenv("OPENLINEAGE_URL", "")


def _ol_enabled() -> bool:
    """Retorna True se OpenLineage estiver disponível e configurado."""
    return _OL_AVAILABLE and bool(_DEFAULT_URL)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_dataset(
    name: str,
    namespace: str | None = None,
    fields: list[dict[str, str]] | None = None,
    is_input: bool = True,
) -> "InputDataset | OutputDataset":
    """
    Constrói um InputDataset ou OutputDataset do OpenLineage.

    Args:
        name:      nome do dataset (ex: "cars", "data/raw/cars.csv")
        namespace: namespace do dataset (ex: "postgres", "file")
        fields:    lista de dicts {"name": ..., "type": ...} com o schema
        is_input:  True para InputDataset, False para OutputDataset
    """
    ns = namespace or _DEFAULT_NAMESPACE
    facets: dict[str, Any] = {}

    if fields:
        facets["schema"] = SchemaDatasetFacet(
            fields=[SchemaField(name=f["name"], type=f.get("type", "STRING"))
                    for f in fields]
        )

    cls = InputDataset if is_input else OutputDataset
    return cls(namespace=ns, name=name, facets=facets)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Cliente principal ─────────────────────────────────────────────────────────

class LineageClient:
    """
    Cliente de linhagem de dados baseado no padrão OpenLineage.

    Emite eventos de START, COMPLETE e FAIL para o backend configurado
    em OPENLINEAGE_URL. Quando a variável não está definida ou o pacote
    não está instalado, todas as operações são no-ops silenciosos.

    Args:
        job_name:  nome do job (ex: "etl_run_pipeline", "train_price_model")
        namespace: namespace do job (default: OPENLINEAGE_NAMESPACE ou "used_cars_ml")
        producer:  URI do produtor (para rastreabilidade da origem do evento)
    """

    def __init__(
        self,
        job_name: str,
        namespace: str | None = None,
        producer: str = "https://github.com/andersonmoura87/used_cars_ml_dashbord",
    ) -> None:
        self.job_name  = job_name
        self.namespace = namespace or _DEFAULT_NAMESPACE
        self.producer  = producer
        self._client   = self._build_client()
        self._run_id: str | None = None

    def _build_client(self) -> "OpenLineageClient | None":
        if not _ol_enabled():
            return None
        try:
            return OpenLineageClient(url=_DEFAULT_URL)
        except Exception as exc:  # pragma: no cover
            logger.warning("Falha ao criar OpenLineageClient: %s", exc)
            return None

    def _emit(self, event: "RunEvent") -> None:
        if self._client is None:
            return
        try:
            self._client.emit(event)
        except Exception as exc:  # pragma: no cover
            logger.warning("Falha ao emitir evento OpenLineage: %s", exc)

    def _make_run(self, run_id: str) -> "Run":
        return Run(runId=run_id)

    def _make_job(self, description: str | None = None) -> "Job":
        facets: dict[str, Any] = {}
        if description:
            facets["documentation"] = DocumentationJobFacet(description=description)
        return Job(namespace=self.namespace, name=self.job_name, facets=facets)

    # ── API pública ────────────────────────────────────────────────────────────

    def _is_ready(self) -> bool:
        """Retorna True se o cliente está pronto para emitir eventos."""
        return _OL_AVAILABLE and self._client is not None

    def start(
        self,
        inputs: list[dict[str, Any]] | None = None,
        outputs: list[dict[str, Any]] | None = None,
        description: str | None = None,
        run_id: str | None = None,
    ) -> str:
        """
        Emite um evento START e retorna o run_id gerado (UUID).

        Args:
            inputs:      lista de datasets de entrada (dicts com name, namespace, fields)
            outputs:     lista de datasets de saída esperados
            description: documentação do job
            run_id:      UUID opcional (gerado automaticamente se omitido)

        Returns:
            run_id: UUID string para usar em complete() ou fail()
        """
        run_id = run_id or str(uuid.uuid4())
        self._run_id = run_id

        if not self._is_ready():
            logger.debug("OpenLineage desabilitado — START de '%s' não emitido", self.job_name)
            return run_id

        in_datasets  = [_make_dataset(is_input=True,  **d) for d in (inputs  or [])]
        out_datasets = [_make_dataset(is_input=False, **d) for d in (outputs or [])]

        event = RunEvent(
            eventType=RunState.START,
            eventTime=_now_iso(),
            run=self._make_run(run_id),
            job=self._make_job(description),
            producer=self.producer,
            inputs=in_datasets,
            outputs=out_datasets,
        )
        self._emit(event)
        logger.info("Lineage START — job=%s run=%s", self.job_name, run_id)
        return run_id

    def complete(
        self,
        run_id: str | None = None,
        outputs: list[dict[str, Any]] | None = None,
    ) -> None:
        """
        Emite um evento COMPLETE.

        Args:
            run_id:  UUID do run (usa o último start() se omitido)
            outputs: datasets de saída com schema final (após execução)
        """
        rid = run_id or self._run_id
        if rid is None:
            logger.warning("complete() chamado sem run_id — chame start() primeiro")
            return

        if not self._is_ready():
            logger.debug("OpenLineage desabilitado — COMPLETE de '%s' não emitido", self.job_name)
            return

        out_datasets = [_make_dataset(is_input=False, **d) for d in (outputs or [])]

        event = RunEvent(
            eventType=RunState.COMPLETE,
            eventTime=_now_iso(),
            run=self._make_run(rid),
            job=self._make_job(),
            producer=self.producer,
            inputs=[],
            outputs=out_datasets,
        )
        self._emit(event)
        logger.info("Lineage COMPLETE — job=%s run=%s", self.job_name, rid)

    def fail(
        self,
        run_id: str | None = None,
        error: str | None = None,
    ) -> None:
        """
        Emite um evento FAIL.

        Args:
            run_id: UUID do run
            error:  mensagem de erro (opcional, para rastreabilidade)
        """
        rid = run_id or self._run_id
        if rid is None:
            logger.warning("fail() chamado sem run_id")
            return

        if not self._is_ready():
            logger.debug("OpenLineage desabilitado — FAIL de '%s' não emitido", self.job_name)
            return

        event = RunEvent(
            eventType=RunState.FAIL,
            eventTime=_now_iso(),
            run=self._make_run(rid),
            job=self._make_job(error),
            producer=self.producer,
            inputs=[],
            outputs=[],
        )
        self._emit(event)
        logger.warning("Lineage FAIL — job=%s run=%s error=%s", self.job_name, rid, error)

    @contextmanager
    def track(
        self,
        inputs: list[dict[str, Any]] | None = None,
        outputs: list[dict[str, Any]] | None = None,
        description: str | None = None,
    ) -> Generator[str, None, None]:
        """
        Context manager que emite START na entrada e COMPLETE/FAIL na saída.

        Uso:
            with client.track(inputs=[...], outputs=[...]) as run_id:
                ...  # lógica do pipeline

        Yields:
            run_id: UUID da execução corrente
        """
        run_id = self.start(inputs=inputs, outputs=outputs, description=description)
        try:
            yield run_id
            self.complete(run_id, outputs=outputs)
        except Exception as exc:
            self.fail(run_id, error=str(exc))
            raise


# ── Datasets padrão do projeto ────────────────────────────────────────────────
# Constantes para reutilização nos pipelines ETL e de treinamento.

RAW_CARS_DATASET = {
    "name": "data/raw/used_cars.csv",
    "namespace": "file",
    "fields": [
        {"name": "id", "type": "STRING"},
        {"name": "price", "type": "DOUBLE"},
        {"name": "year", "type": "INTEGER"},
        {"name": "manufacturer", "type": "STRING"},
        {"name": "model", "type": "STRING"},
        {"name": "condition", "type": "STRING"},
        {"name": "fuel", "type": "STRING"},
        {"name": "odometer", "type": "DOUBLE"},
        {"name": "transmission", "type": "STRING"},
        {"name": "state", "type": "STRING"},
    ],
}

CLEAN_CARS_DATASET = {
    "name": "cars",
    "namespace": "postgres://used_cars",
    "fields": [
        {"name": "id", "type": "INTEGER"},
        {"name": "price", "type": "DOUBLE"},
        {"name": "year", "type": "INTEGER"},
        {"name": "manufacturer", "type": "STRING"},
        {"name": "model", "type": "STRING"},
        {"name": "odometer", "type": "DOUBLE"},
        {"name": "has_installments", "type": "BOOLEAN"},
    ],
}

MANUFACTURER_STATS_DATASET = {
    "name": "manufacturer_stats",
    "namespace": "postgres://used_cars",
    "fields": [
        {"name": "manufacturer", "type": "STRING"},
        {"name": "avg_price", "type": "DOUBLE"},
        {"name": "total_listings", "type": "INTEGER"},
    ],
}

MODEL_FILE_DATASET = {
    "name": "models/price_model.joblib",
    "namespace": "file",
    "fields": [
        {"name": "model_type", "type": "STRING"},
        {"name": "version", "type": "STRING"},
        {"name": "r2_score", "type": "DOUBLE"},
        {"name": "rmse", "type": "DOUBLE"},
    ],
}
