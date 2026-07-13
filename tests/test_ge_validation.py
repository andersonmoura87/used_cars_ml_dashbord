"""
Testes unitários para src/etl/ge_validation.py.

Estratégia: os testes NÃO requerem great_expectations instalado.
Quando GE não está disponível (_GE_AVAILABLE=False ou GE_ENABLED=false),
validate_raw() e validate_clean() devem retornar True imediatamente.

Quando GE está disponível, _run_ge_validation() é mockado para retornar
resultados pré-fabricados, permitindo validar o fluxo completo sem servidor GE.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def raw_df() -> pd.DataFrame:
    """DataFrame mínimo que representa dados brutos (pós-extração)."""
    rng = np.random.default_rng(0)
    n = 2_000
    return pd.DataFrame({
        "price":        rng.integers(1_000, 50_000, n).astype(float),
        "year":         rng.integers(2000, 2023, n),
        "odometer":     rng.integers(0, 200_000, n).astype(float),
        "manufacturer": rng.choice(["toyota", "honda", "ford"], n),
        "state":        rng.choice(["ca", "tx", "ny"], n),
        "fuel":         rng.choice(["gas", "diesel"], n),
        "transmission": rng.choice(["automatic", "manual"], n),
    })


@pytest.fixture
def clean_df(raw_df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame mínimo que representa dados limpos (pós-transformação)."""
    df = raw_df.copy()
    df["vehicle_age"] = 2024 - df["year"]
    return df


def _ge_result(success: bool, passed: int = 10, failed: int = 0) -> Dict[str, Any]:
    """Constrói um resultado GE fake no formato JSON."""
    results = []
    for i in range(passed):
        results.append({
            "success": True,
            "expectation_config": {
                "expectation_type": f"expect_column_to_exist",
                "kwargs": {"column": f"col_{i}"},
            },
        })
    for i in range(failed):
        results.append({
            "success": False,
            "expectation_config": {
                "expectation_type": "expect_column_values_to_be_between",
                "kwargs": {"column": f"bad_col_{i}"},
            },
        })
    return {
        "success": success,
        "statistics": {
            "evaluated_expectations": passed + failed,
            "successful_expectations": passed,
            "unsuccessful_expectations": failed,
        },
        "results": results,
    }


# ── _ge_enabled() ──────────────────────────────────────────────────────────────

class TestGeEnabled:
    def test_disabled_when_env_false(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GE_ENABLED", "false")
        from src.etl.ge_validation import _ge_enabled
        assert _ge_enabled() is False

    def test_disabled_when_env_0(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GE_ENABLED", "0")
        from src.etl.ge_validation import _ge_enabled
        assert _ge_enabled() is False

    def test_enabled_when_env_true(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("GE_ENABLED", "true")
        from src.etl.ge_validation import _ge_enabled
        from src.etl.ge_validation import _GE_AVAILABLE
        assert _ge_enabled() == _GE_AVAILABLE

    def test_enabled_by_default(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("GE_ENABLED", raising=False)
        from src.etl.ge_validation import _ge_enabled, _GE_AVAILABLE
        assert _ge_enabled() == _GE_AVAILABLE


# ── validate_raw() quando GE desabilitado ────────────────────────────────────

class TestValidateRawDisabled:
    def test_returns_true_when_ge_disabled(
        self, raw_df: pd.DataFrame, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("GE_ENABLED", "false")
        with patch("src.etl.ge_validation._ge_enabled", return_value=False):
            from src.etl.ge_validation import validate_raw
            result = validate_raw(raw_df)
        assert result is True

    def test_no_exception_when_ge_disabled(
        self, raw_df: pd.DataFrame
    ):
        with patch("src.etl.ge_validation._ge_enabled", return_value=False):
            from src.etl.ge_validation import validate_raw
            result = validate_raw(raw_df, raise_on_failure=True)
        assert result is True


# ── validate_raw() com GE mockado ────────────────────────────────────────────

class TestValidateRawMocked:
    def test_returns_true_when_all_pass(
        self, raw_df: pd.DataFrame, tmp_path: Path
    ):
        ge_result = _ge_result(success=True, passed=14, failed=0)
        with patch("src.etl.ge_validation._ge_enabled", return_value=True), \
             patch("src.etl.ge_validation._run_ge_validation", return_value=ge_result), \
             patch("src.etl.ge_validation._VALIDATIONS_DIR", tmp_path):
            from src.etl.ge_validation import validate_raw
            result = validate_raw(raw_df)
        assert result is True

    def test_returns_false_when_expectations_fail(
        self, raw_df: pd.DataFrame, tmp_path: Path
    ):
        ge_result = _ge_result(success=False, passed=10, failed=4)
        with patch("src.etl.ge_validation._ge_enabled", return_value=True), \
             patch("src.etl.ge_validation._run_ge_validation", return_value=ge_result), \
             patch("src.etl.ge_validation._VALIDATIONS_DIR", tmp_path):
            from src.etl.ge_validation import validate_raw
            result = validate_raw(raw_df, raise_on_failure=False)
        assert result is False

    def test_raises_when_raise_on_failure_true(
        self, raw_df: pd.DataFrame, tmp_path: Path
    ):
        ge_result = _ge_result(success=False, passed=10, failed=4)
        with patch("src.etl.ge_validation._ge_enabled", return_value=True), \
             patch("src.etl.ge_validation._run_ge_validation", return_value=ge_result), \
             patch("src.etl.ge_validation._VALIDATIONS_DIR", tmp_path):
            from src.etl.ge_validation import validate_raw
            with pytest.raises(ValueError, match="Validação GE falhou"):
                validate_raw(raw_df, raise_on_failure=True)

    def test_saves_json_result(
        self, raw_df: pd.DataFrame, tmp_path: Path
    ):
        ge_result = _ge_result(success=True, passed=14, failed=0)
        with patch("src.etl.ge_validation._ge_enabled", return_value=True), \
             patch("src.etl.ge_validation._run_ge_validation", return_value=ge_result), \
             patch("src.etl.ge_validation._VALIDATIONS_DIR", tmp_path):
            from src.etl.ge_validation import validate_raw
            validate_raw(raw_df)

        saved = list(tmp_path.glob("raw_cars_suite_*.json"))
        assert len(saved) == 1
        content = json.loads(saved[0].read_text())
        assert content["success"] is True

    def test_exception_during_validation_does_not_raise(
        self, raw_df: pd.DataFrame
    ):
        """Erro interno de GE não deve vazar — apenas loga warning."""
        with patch("src.etl.ge_validation._ge_enabled", return_value=True), \
             patch("src.etl.ge_validation._run_ge_validation",
                   side_effect=RuntimeError("GE internal error")):
            from src.etl.ge_validation import validate_raw
            result = validate_raw(raw_df, raise_on_failure=False)
        assert result is False

    def test_exception_propagates_when_raise_on_failure(
        self, raw_df: pd.DataFrame
    ):
        with patch("src.etl.ge_validation._ge_enabled", return_value=True), \
             patch("src.etl.ge_validation._run_ge_validation",
                   side_effect=RuntimeError("GE internal error")):
            from src.etl.ge_validation import validate_raw
            with pytest.raises(RuntimeError):
                validate_raw(raw_df, raise_on_failure=True)


# ── validate_clean() com GE mockado ──────────────────────────────────────────

class TestValidateCleanMocked:
    def test_returns_true_when_all_pass(
        self, clean_df: pd.DataFrame, tmp_path: Path
    ):
        ge_result = _ge_result(success=True, passed=11, failed=0)
        with patch("src.etl.ge_validation._ge_enabled", return_value=True), \
             patch("src.etl.ge_validation._run_ge_validation", return_value=ge_result), \
             patch("src.etl.ge_validation._VALIDATIONS_DIR", tmp_path):
            from src.etl.ge_validation import validate_clean
            result = validate_clean(clean_df)
        assert result is True

    def test_saves_json_for_clean_suite(
        self, clean_df: pd.DataFrame, tmp_path: Path
    ):
        ge_result = _ge_result(success=True, passed=11, failed=0)
        with patch("src.etl.ge_validation._ge_enabled", return_value=True), \
             patch("src.etl.ge_validation._run_ge_validation", return_value=ge_result), \
             patch("src.etl.ge_validation._VALIDATIONS_DIR", tmp_path):
            from src.etl.ge_validation import validate_clean
            validate_clean(clean_df)

        saved = list(tmp_path.glob("clean_cars_suite_*.json"))
        assert len(saved) == 1

    def test_raises_by_default_when_clean_fails(
        self, clean_df: pd.DataFrame, tmp_path: Path
    ):
        """validate_clean() com raise_on_failure=True lança ValueError."""
        ge_result = _ge_result(success=False, passed=8, failed=3)
        with patch("src.etl.ge_validation._ge_enabled", return_value=True), \
             patch("src.etl.ge_validation._run_ge_validation", return_value=ge_result), \
             patch("src.etl.ge_validation._VALIDATIONS_DIR", tmp_path):
            from src.etl.ge_validation import validate_clean
            with pytest.raises(ValueError, match="Validação GE falhou"):
                validate_clean(clean_df, raise_on_failure=True)


# ── _raw_expectations() e _clean_expectations() ───────────────────────────────

class TestExpectationDefinitions:
    def test_raw_expectations_not_empty(self):
        from src.etl.ge_validation import _raw_expectations
        exps = _raw_expectations()
        assert len(exps) >= 10
        types = {e["expectation_type"] for e in exps}
        assert "expect_column_to_exist" in types
        assert "expect_table_row_count_to_be_between" in types

    def test_clean_expectations_stricter_nullability(self):
        """Dados limpos devem ter mostly >= 0.95 em nulls vs 0.70 nos brutos."""
        from src.etl.ge_validation import _raw_expectations, _clean_expectations
        def get_null_mostly(exps, col):
            for e in exps:
                if (e["expectation_type"] == "expect_column_values_to_not_be_null"
                        and e["kwargs"].get("column") == col):
                    return e["kwargs"].get("mostly", 1.0)
            return None

        raw_price_mostly = get_null_mostly(_raw_expectations(), "price")
        clean_price_mostly = get_null_mostly(_clean_expectations(), "price")
        assert clean_price_mostly > raw_price_mostly

    def test_clean_has_vehicle_age_column(self):
        from src.etl.ge_validation import _clean_expectations
        cols = [
            e["kwargs"].get("column")
            for e in _clean_expectations()
            if e["expectation_type"] == "expect_column_to_exist"
        ]
        assert "vehicle_age" in cols

    def test_raw_price_range_allows_zero(self):
        from src.etl.ge_validation import _raw_expectations
        for e in _raw_expectations():
            if (e["expectation_type"] == "expect_column_values_to_be_between"
                    and e["kwargs"].get("column") == "price"):
                assert e["kwargs"]["min_value"] == 0
                break

    def test_clean_price_range_excludes_near_zero(self):
        """Dados limpos não devem aceitar preços próximos de zero."""
        from src.etl.ge_validation import _clean_expectations
        for e in _clean_expectations():
            if (e["expectation_type"] == "expect_column_values_to_be_between"
                    and e["kwargs"].get("column") == "price"):
                assert e["kwargs"]["min_value"] > 0
                break


# ── _log_summary() ────────────────────────────────────────────────────────────

class TestLogSummary:
    def test_returns_true_on_success(self):
        from src.etl.ge_validation import _log_summary
        result = _ge_result(success=True, passed=10, failed=0)
        assert _log_summary(result, "test_suite") is True

    def test_returns_false_on_failure(self):
        from src.etl.ge_validation import _log_summary
        result = _ge_result(success=False, passed=8, failed=2)
        assert _log_summary(result, "test_suite") is False
