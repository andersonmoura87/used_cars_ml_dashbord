"""
Testes unitários para scripts/check_drift.py.

Cobre:
  - KS test: sem drift, com drift, dados insuficientes
  - PSI: sem drift, com drift, dados insuficientes
  - Agregação: drifted_features, drift_score
  - check_drift(): criação de referência quando não existe
  - check_drift(): sem drift quando distribuições iguais
  - check_drift(): com drift quando distribuições diferentes
  - _write_github_outputs(): escrita no GITHUB_OUTPUT
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.check_drift import (
    _aggregate_drift,
    _ks_test,
    _psi,
    _write_github_outputs,
    check_drift,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_df(n: int = 500, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "year":         rng.integers(2010, 2023, n),
        "odometer":     rng.integers(1_000, 200_000, n).astype(float),
        "vehicle_age":  rng.integers(0, 13, n).astype(float),
        "price":        rng.uniform(5_000, 40_000, n),
        "manufacturer": rng.choice(["toyota", "ford", "honda", "chevrolet"], n),
        "condition":    rng.choice(["good", "excellent", "fair"], n),
        "fuel":         rng.choice(["gas", "diesel", "electric"], n),
        "transmission": rng.choice(["automatic", "manual"], n),
        "drive":        rng.choice(["4wd", "fwd", "rwd"], n),
        "type":         rng.choice(["sedan", "SUV", "pickup"], n),
        "state":        rng.choice(["ca", "tx", "fl", "ny"], n),
    })


def _make_drifted_df(n: int = 500, seed: int = 99) -> pd.DataFrame:
    """Distribução muito diferente da referência."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "year":         rng.integers(2018, 2024, n),          # apenas carros novos
        "odometer":     rng.integers(100, 20_000, n).astype(float),  # muito baixo
        "vehicle_age":  rng.integers(0, 6, n).astype(float),
        "price":        rng.uniform(30_000, 80_000, n),        # faixa muito diferente
        "manufacturer": rng.choice(["bmw", "audi", "mercedes", "tesla"], n),  # marcas novas
        "condition":    rng.choice(["excellent", "like new"], n),
        "fuel":         rng.choice(["electric", "hybrid"], n),
        "transmission": rng.choice(["automatic"], n),
        "drive":        rng.choice(["4wd"], n),
        "type":         rng.choice(["SUV", "truck"], n),
        "state":        rng.choice(["wa", "or", "id"], n),
    })


# ── KS test ───────────────────────────────────────────────────────────────────

class TestKsTest:
    def test_no_drift_identical(self):
        rng = np.random.default_rng(0)
        s = pd.Series(rng.normal(0, 1, 1000))
        result = _ks_test(s, s)
        assert result["drift"] is False
        assert result["p_value"] == pytest.approx(1.0, abs=0.01)

    def test_no_drift_same_dist(self):
        rng = np.random.default_rng(0)
        ref = pd.Series(rng.normal(50_000, 10_000, 2000))
        cur = pd.Series(rng.normal(50_000, 10_000, 2000))
        result = _ks_test(ref, cur)
        # distribuições idênticas → sem drift (p_value alto)
        assert result["drift"] is False

    def test_drift_different_dist(self):
        rng = np.random.default_rng(1)
        ref = pd.Series(rng.normal(10_000, 500, 500))
        cur = pd.Series(rng.normal(80_000, 500, 500))  # média completamente diferente
        result = _ks_test(ref, cur)
        assert result["drift"] is True
        assert result["p_value"] < 0.05

    def test_insufficient_data(self):
        ref = pd.Series([1.0, 2.0, 3.0])
        cur = pd.Series([4.0, 5.0])
        result = _ks_test(ref, cur)
        assert result["statistic"] is None
        assert result["drift"] is False
        assert result["reason"] == "insufficient_data"

    def test_all_nan(self):
        ref = pd.Series([np.nan] * 100)
        cur = pd.Series([np.nan] * 100)
        result = _ks_test(ref, cur)
        assert result["drift"] is False


# ── PSI ───────────────────────────────────────────────────────────────────────

class TestPsi:
    def test_no_drift_identical(self):
        rng = np.random.default_rng(2)
        cats = ["toyota", "ford", "honda"]
        s = pd.Series(rng.choice(cats, 1000))
        result = _psi(s, s)
        assert result["drift"] is False
        assert result["psi"] < 0.20

    def test_drift_new_categories(self):
        ref = pd.Series(["toyota"] * 500 + ["ford"] * 500)
        cur = pd.Series(["bmw"] * 500 + ["audi"] * 500)
        result = _psi(ref, cur)
        assert result["drift"] is True
        assert result["psi"] > 0.20

    def test_top_categories_returned(self):
        ref = pd.Series(["a"] * 400 + ["b"] * 300 + ["c"] * 300)
        cur = pd.Series(["a"] * 100 + ["b"] * 100 + ["c"] * 800)
        result = _psi(ref, cur)
        assert "top_categories" in result
        assert len(result["top_categories"]) <= 5

    def test_insufficient_data(self):
        ref = pd.Series([], dtype=str)
        cur = pd.Series(["toyota"])
        result = _psi(ref, cur)
        assert result["drift"] is False
        assert result["reason"] == "insufficient_data"


# ── Agregação ─────────────────────────────────────────────────────────────────

class TestAggregateDrift:
    def test_no_features(self):
        detected, score, drifted = _aggregate_drift({}, {}, 0.05, 0.20)
        assert detected is False
        assert score == 0.0
        assert drifted == []

    def test_some_drifted(self):
        numerical = {
            "price":    {"p_value": 0.001, "drift": True},
            "odometer": {"p_value": 0.80,  "drift": False},
        }
        categorical = {
            "manufacturer": {"psi": 0.35, "drift": True},
            "condition":    {"psi": 0.05, "drift": False},
        }
        detected, score, drifted = _aggregate_drift(numerical, categorical, 0.05, 0.20)
        assert detected is True
        assert "price" in drifted
        assert "manufacturer" in drifted
        assert score > 0.0

    def test_all_ok(self):
        numerical    = {"price": {"p_value": 0.5, "drift": False}}
        categorical  = {"manufacturer": {"psi": 0.05, "drift": False}}
        detected, score, drifted = _aggregate_drift(numerical, categorical, 0.05, 0.20)
        assert detected is False
        assert drifted == []

    def test_none_values_skipped(self):
        numerical = {"price": {"p_value": None, "drift": False}}
        categorical = {"manufacturer": {"psi": None, "drift": False}}
        detected, score, drifted = _aggregate_drift(numerical, categorical, 0.05, 0.20)
        assert score == 0.0
        assert detected is False


# ── check_drift() integração ──────────────────────────────────────────────────

class TestCheckDrift:
    def test_creates_reference_when_missing(self, tmp_path):
        ref_path     = tmp_path / "reference.parquet"
        current_path = tmp_path / "current.csv"
        report_dir   = tmp_path / "quality"

        df = _make_df(200)
        df.to_csv(current_path, index=False)

        report = check_drift(
            current_path=current_path,
            reference_path=ref_path,
            report_dir=report_dir,
        )

        assert report["drift_detected"] is False
        assert report["status"] == "reference_created"
        assert ref_path.exists(), "Deve criar o arquivo de referência"

    def test_no_drift_same_data(self, tmp_path):
        ref_path     = tmp_path / "reference.parquet"
        current_path = tmp_path / "current.csv"
        report_dir   = tmp_path / "quality"

        df = _make_df(1000)
        df.to_parquet(ref_path, index=False)
        df.to_csv(current_path, index=False)

        report = check_drift(
            current_path=current_path,
            reference_path=ref_path,
            report_dir=report_dir,
        )
        assert report["drift_detected"] is False
        assert report["drift_score"] < 0.01

    def test_drift_detected_different_data(self, tmp_path):
        ref_path     = tmp_path / "reference.parquet"
        current_path = tmp_path / "current.csv"
        report_dir   = tmp_path / "quality"

        _make_df(1000, seed=0).to_parquet(ref_path, index=False)
        _make_drifted_df(1000, seed=99).to_csv(current_path, index=False)

        report = check_drift(
            current_path=current_path,
            reference_path=ref_path,
            report_dir=report_dir,
        )
        assert report["drift_detected"] is True
        assert len(report["drifted_features"]) > 0

    def test_saves_report_json(self, tmp_path):
        ref_path     = tmp_path / "reference.parquet"
        current_path = tmp_path / "current.csv"
        report_dir   = tmp_path / "quality"

        df = _make_df(200)
        df.to_parquet(ref_path, index=False)
        df.to_csv(current_path, index=False)

        check_drift(
            current_path=current_path,
            reference_path=ref_path,
            report_dir=report_dir,
        )
        reports = list(report_dir.glob("drift_report_*.json"))
        assert len(reports) == 1
        with open(reports[0]) as f:
            saved = json.load(f)
        assert "drift_detected" in saved
        assert "numerical" in saved
        assert "categorical" in saved

    def test_save_reference_flag(self, tmp_path):
        ref_path     = tmp_path / "reference.parquet"
        current_path = tmp_path / "current.csv"
        report_dir   = tmp_path / "quality"

        old_df = _make_df(500, seed=0)
        new_df = _make_drifted_df(500, seed=1)
        old_df.to_parquet(ref_path, index=False)
        new_df.to_csv(current_path, index=False)

        old_mtime = ref_path.stat().st_mtime
        check_drift(
            current_path=current_path,
            reference_path=ref_path,
            report_dir=report_dir,
            save_reference=True,
        )
        assert ref_path.stat().st_mtime >= old_mtime


# ── _write_github_outputs ─────────────────────────────────────────────────────

class TestWriteGithubOutputs:
    def test_writes_to_file(self, tmp_path):
        out_file = tmp_path / "github_output.txt"
        report = {
            "drift_detected": True,
            "drift_score": 0.42,
            "drifted_features": ["price", "manufacturer"],
        }
        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(out_file)}):
            _write_github_outputs(report)

        content = out_file.read_text()
        assert "drift_detected=true" in content
        assert "drift_score=0.42" in content
        assert "price" in content

    def test_no_github_output_env(self):
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_OUTPUT"}
        with patch.dict(os.environ, env, clear=True):
            _write_github_outputs({"drift_detected": False, "drift_score": 0.0, "drifted_features": []})
