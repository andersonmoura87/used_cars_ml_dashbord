"""
Great Expectations — validação de qualidade de dados para o pipeline ETL.

Dois pontos de validação:
  1. validate_raw()   — dados brutos logo após a extração
  2. validate_clean() — dados transformados antes do carregamento

A validação é OPCIONAL: se `great_expectations` não estiver instalado ou
GE_ENABLED=false, o pipeline continua sem interrupção (apenas warning).

Os resultados são salvos em gx/uncommitted/validations/ como JSON.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent.parent
_VALIDATIONS_DIR = _ROOT / "gx" / "uncommitted" / "validations"

try:
    import great_expectations as gx
    from great_expectations.core import ExpectationSuite, ExpectationConfiguration

    _GE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _GE_AVAILABLE = False


def _ge_enabled() -> bool:
    return _GE_AVAILABLE and os.getenv("GE_ENABLED", "true").lower() != "false"


# ── Definições de expectativas ────────────────────────────────────────────────

def _raw_expectations() -> list[dict]:
    """Suite de expectativas para dados BRUTOS (pós-extração)."""
    current_year = datetime.now().year
    return [
        # Existência de colunas obrigatórias
        {"expectation_type": "expect_column_to_exist", "kwargs": {"column": "price"}},
        {"expectation_type": "expect_column_to_exist", "kwargs": {"column": "year"}},
        {"expectation_type": "expect_column_to_exist", "kwargs": {"column": "odometer"}},
        {"expectation_type": "expect_column_to_exist", "kwargs": {"column": "manufacturer"}},
        {"expectation_type": "expect_column_to_exist", "kwargs": {"column": "state"}},
        {"expectation_type": "expect_column_to_exist", "kwargs": {"column": "fuel"}},
        {"expectation_type": "expect_column_to_exist", "kwargs": {"column": "transmission"}},
        # Nulidade — tolerância alta nos dados brutos
        {"expectation_type": "expect_column_values_to_not_be_null",
         "kwargs": {"column": "price", "mostly": 0.70}},
        {"expectation_type": "expect_column_values_to_not_be_null",
         "kwargs": {"column": "year", "mostly": 0.90}},
        {"expectation_type": "expect_column_values_to_not_be_null",
         "kwargs": {"column": "odometer", "mostly": 0.70}},
        # Intervalos de valores
        {"expectation_type": "expect_column_values_to_be_between",
         "kwargs": {"column": "price", "min_value": 0, "max_value": 1_000_000, "mostly": 0.95}},
        {"expectation_type": "expect_column_values_to_be_between",
         "kwargs": {"column": "year", "min_value": 1900, "max_value": current_year + 1, "mostly": 0.99}},
        {"expectation_type": "expect_column_values_to_be_between",
         "kwargs": {"column": "odometer", "min_value": 0, "max_value": 1_500_000, "mostly": 0.99}},
        # Valores categóricos esperados
        {"expectation_type": "expect_column_values_to_be_in_set",
         "kwargs": {"column": "fuel",
                    "value_set": ["gas", "diesel", "hybrid", "electric", "other"],
                    "mostly": 0.90}},
        {"expectation_type": "expect_column_values_to_be_in_set",
         "kwargs": {"column": "transmission",
                    "value_set": ["automatic", "manual", "other"],
                    "mostly": 0.90}},
        # Volume mínimo
        {"expectation_type": "expect_table_row_count_to_be_between",
         "kwargs": {"min_value": 1_000, "max_value": 10_000_000}},
    ]


def _clean_expectations() -> list[dict]:
    """Suite de expectativas para dados LIMPOS (pós-transformação)."""
    current_year = datetime.now().year
    return [
        # Colunas obrigatórias presentes
        {"expectation_type": "expect_column_to_exist", "kwargs": {"column": "price"}},
        {"expectation_type": "expect_column_to_exist", "kwargs": {"column": "year"}},
        {"expectation_type": "expect_column_to_exist", "kwargs": {"column": "odometer"}},
        {"expectation_type": "expect_column_to_exist", "kwargs": {"column": "vehicle_age"}},
        # Sem nulos nas colunas críticas (tolerância menor após limpeza)
        {"expectation_type": "expect_column_values_to_not_be_null",
         "kwargs": {"column": "price", "mostly": 0.99}},
        {"expectation_type": "expect_column_values_to_not_be_null",
         "kwargs": {"column": "year", "mostly": 0.99}},
        {"expectation_type": "expect_column_values_to_not_be_null",
         "kwargs": {"column": "odometer", "mostly": 0.95}},
        # Intervalos mais restritos após limpeza
        {"expectation_type": "expect_column_values_to_be_between",
         "kwargs": {"column": "price", "min_value": 100, "max_value": 500_000, "mostly": 0.99}},
        {"expectation_type": "expect_column_values_to_be_between",
         "kwargs": {"column": "year", "min_value": 1980, "max_value": current_year + 1, "mostly": 0.99}},
        {"expectation_type": "expect_column_values_to_be_between",
         "kwargs": {"column": "odometer", "min_value": 0, "max_value": 500_000, "mostly": 0.95}},
        # Volume mínimo pós-limpeza (pelo menos 50% do bruto esperado)
        {"expectation_type": "expect_table_row_count_to_be_between",
         "kwargs": {"min_value": 500, "max_value": 10_000_000}},
    ]


# ── Executor de validação ─────────────────────────────────────────────────────

def _run_ge_validation(
    df: pd.DataFrame,
    suite_name: str,
    expectations: list[dict],
) -> Dict[str, Any]:
    """Executa as expectativas num DataFrame usando contexto efêmero do GE."""
    context = gx.get_context(mode="ephemeral")

    # Datasource pandas
    datasource = context.sources.add_pandas(f"{suite_name}_source")
    asset = datasource.add_dataframe_asset(f"{suite_name}_asset")
    batch_request = asset.build_batch_request(dataframe=df)

    # Suite
    suite = context.add_expectation_suite(suite_name)
    for exp in expectations:
        suite.add_expectation(
            ExpectationConfiguration(
                expectation_type=exp["expectation_type"],
                kwargs=exp["kwargs"],
            )
        )

    # Validator + validação
    validator = context.get_validator(
        batch_request=batch_request,
        expectation_suite_name=suite_name,
    )
    result = validator.validate()
    return result.to_json_dict()


def _save_result(result: Dict[str, Any], suite_name: str) -> Path:
    """Persiste o resultado da validação como JSON."""
    _VALIDATIONS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = _VALIDATIONS_DIR / f"{suite_name}_{ts}.json"
    path.write_text(json.dumps(result, indent=2, default=str))
    return path


def _log_summary(result: Dict[str, Any], suite_name: str) -> bool:
    """Loga resumo humano e retorna True se passou."""
    stats = result.get("statistics", {})
    evaluated = stats.get("evaluated_expectations", 0)
    successful = stats.get("successful_expectations", 0)
    failed = stats.get("unsuccessful_expectations", 0)
    success = result.get("success", False)

    level = logging.INFO if success else logging.WARNING
    logger.log(
        level,
        "[GE] %s — %d/%d expectativas passaram%s",
        suite_name,
        successful,
        evaluated,
        "" if success else f" | {failed} FALHARAM",
    )

    if not success:
        for res in result.get("results", []):
            if not res.get("success"):
                exp_type = res["expectation_config"]["expectation_type"]
                col = res["expectation_config"]["kwargs"].get("column", "table")
                logger.warning("  ✗ [%s] %s — %s", suite_name, exp_type, col)

    return success


# ── API pública ───────────────────────────────────────────────────────────────

def validate_raw(df: pd.DataFrame, raise_on_failure: bool = False) -> bool:
    """
    Valida dados brutos (pós-extração).

    Args:
        df:               DataFrame a validar.
        raise_on_failure: Se True, lança ValueError quando a suite falha.
                          Default False — apenas loga warning (pipeline continua).
    Returns:
        True se todas as expectativas passaram, False caso contrário.
    """
    if not _ge_enabled():
        logger.info("[GE] Desabilitado — pulando validação de dados brutos.")
        return True

    try:
        result = _run_ge_validation(df, "raw_cars_suite", _raw_expectations())
        path = _save_result(result, "raw_cars_suite")
        passed = _log_summary(result, "raw_cars_suite")
        logger.info("[GE] Resultado salvo em %s", path)

        if not passed and raise_on_failure:
            raise ValueError(
                f"Validação GE falhou para dados brutos. "
                f"Verifique {path} para detalhes."
            )
        return passed
    except Exception as exc:
        if raise_on_failure:
            raise
        logger.warning("[GE] Erro durante validação raw: %s", exc)
        return False


def validate_clean(df: pd.DataFrame, raise_on_failure: bool = False) -> bool:
    """
    Valida dados limpos (pós-transformação, pré-carga).

    Args:
        df:               DataFrame a validar.
        raise_on_failure: Se True, lança ValueError quando a suite falha.
                          Default False — apenas loga warning.
    Returns:
        True se todas as expectativas passaram, False caso contrário.
    """
    if not _ge_enabled():
        logger.info("[GE] Desabilitado — pulando validação de dados limpos.")
        return True

    try:
        result = _run_ge_validation(df, "clean_cars_suite", _clean_expectations())
        path = _save_result(result, "clean_cars_suite")
        passed = _log_summary(result, "clean_cars_suite")
        logger.info("[GE] Resultado salvo em %s", path)

        if not passed and raise_on_failure:
            raise ValueError(
                f"Validação GE falhou para dados limpos. "
                f"Verifique {path} para detalhes."
            )
        return passed
    except Exception as exc:
        if raise_on_failure:
            raise
        logger.warning("[GE] Erro durante validação clean: %s", exc)
        return False
