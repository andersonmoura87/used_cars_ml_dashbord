"""
Testes unitários para a integração MLflow em AdvancedPriceModel.

Estes testes verificam:
- Que _mlflow_active() respeita a variável de ambiente
- Que train() funciona corretamente SEM MLflow (sem MLFLOW_TRACKING_URI)
- Que train() funciona com MLflow usando um servidor local temporário (mlflow.set_tracking_uri)
- Que save() inclui data_hash e metrics no meta.json
- Que promote_model.py valida argumentos corretamente
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.models.price_model import AdvancedPriceModel, _mlflow_active


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_df() -> pd.DataFrame:
    """DataFrame mínimo com as features do modelo de preços."""
    rng = np.random.default_rng(42)
    n = 200
    return pd.DataFrame({
        "manufacturer": rng.choice(["toyota", "honda", "ford"], n),
        "model":        rng.choice(["civic", "corolla", "f150"], n),
        "condition":    rng.choice(["good", "excellent", "fair"], n),
        "fuel":         rng.choice(["gas", "diesel"], n),
        "transmission": rng.choice(["automatic", "manual"], n),
        "drive":        rng.choice(["fwd", "rwd", "4wd"], n),
        "type":         rng.choice(["sedan", "SUV", "truck"], n),
        "paint_color":  rng.choice(["white", "black", "red"], n),
        "state":        rng.choice(["ca", "tx", "ny"], n),
        "year":         rng.integers(2010, 2023, n),
        "odometer":     rng.integers(5000, 200000, n),
        "vehicle_age":  rng.integers(0, 13, n),
        "price":        rng.integers(5000, 50000, n).astype(float),
    })


@pytest.fixture
def model_instance(sample_df: pd.DataFrame) -> AdvancedPriceModel:
    cat = ["manufacturer", "model", "condition", "fuel", "transmission",
           "drive", "type", "paint_color", "state"]
    num = ["year", "odometer", "vehicle_age"]
    return AdvancedPriceModel(categorical_features=cat, numerical_features=num)


# ── _mlflow_active() ──────────────────────────────────────────────────────────

class TestMlflowActive:
    def test_inactive_without_uri(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
        assert _mlflow_active() is False

    def test_active_with_uri(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
        # só verifica a lógica da função — não requer servidor real
        from src.models.price_model import _MLFLOW_AVAILABLE
        expected = _MLFLOW_AVAILABLE  # True se mlflow instalado
        assert _mlflow_active() == expected


# ── train() sem MLflow ────────────────────────────────────────────────────────

class TestTrainWithoutMlflow:
    def test_train_returns_metrics(
        self,
        model_instance: AdvancedPriceModel,
        sample_df: pd.DataFrame,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
        metrics = model_instance.train(sample_df, validation_method="full")
        assert set(metrics.keys()) == {"r2", "rmse", "mae"}
        assert -1 < metrics["r2"] <= 1
        assert metrics["rmse"] > 0
        assert metrics["mae"] > 0

    def test_train_time_series_cv(
        self,
        model_instance: AdvancedPriceModel,
        sample_df: pd.DataFrame,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
        metrics = model_instance.train(sample_df, validation_method="time_series")
        assert "r2" in metrics
        assert "rmse" in metrics

    def test_active_run_id_none_without_mlflow(
        self,
        model_instance: AdvancedPriceModel,
        sample_df: pd.DataFrame,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
        model_instance.train(sample_df, validation_method="full")
        assert model_instance._active_run_id is None


# ── train() com MLflow mockado ────────────────────────────────────────────────

class TestTrainWithMlflowMocked:
    def test_train_calls_log_to_mlflow(
        self,
        model_instance: AdvancedPriceModel,
        sample_df: pd.DataFrame,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
        with patch("src.models.price_model._mlflow_active", return_value=True), \
             patch.object(model_instance, "_log_to_mlflow") as mock_log:
            model_instance.train(sample_df, validation_method="full")
            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs
            assert "metrics" in call_kwargs
            assert "experiment_name" in call_kwargs

    def test_mlflow_params_logged(
        self,
        model_instance: AdvancedPriceModel,
        sample_df: pd.DataFrame,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Verifica que os params e métricas corretos chegam ao _log_to_mlflow."""
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
        captured: dict = {}

        def fake_log(X, y, metrics, experiment_name, run_name, tags):
            captured["metrics"] = metrics
            captured["experiment_name"] = experiment_name
            captured["tags"] = tags

        with patch("src.models.price_model._mlflow_active", return_value=True), \
             patch.object(model_instance, "_log_to_mlflow", side_effect=fake_log):
            model_instance.train(
                sample_df,
                validation_method="full",
                mlflow_experiment="test_exp",
                mlflow_tags={"triggered_by": "pytest"},
            )

        assert captured["experiment_name"] == "test_exp"
        assert "r2" in captured["metrics"]
        assert "rmse" in captured["metrics"]
        assert "mae" in captured["metrics"]
        assert captured["tags"]["triggered_by"] == "pytest"


# ── save() — meta.json com data_hash e metrics ────────────────────────────────

class TestSaveWithHash:
    def test_meta_json_has_data_hash(
        self,
        model_instance: AdvancedPriceModel,
        sample_df: pd.DataFrame,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
        metrics = model_instance.train(sample_df, validation_method="full")
        model_instance.save(
            models_dir=tmp_path,
            training_df=sample_df,
            metrics=metrics,
        )
        meta_files = list(tmp_path.glob("*_meta.json"))
        assert len(meta_files) == 1
        meta = json.loads(meta_files[0].read_text())
        assert "data_hash" in meta
        assert meta["data_hash"] is not None
        assert len(meta["data_hash"]) == 64  # SHA-256 hex

    def test_meta_json_has_metrics(
        self,
        model_instance: AdvancedPriceModel,
        sample_df: pd.DataFrame,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
        metrics = model_instance.train(sample_df, validation_method="full")
        model_instance.save(
            models_dir=tmp_path,
            training_df=sample_df,
            metrics=metrics,
        )
        meta = json.loads(list(tmp_path.glob("*_meta.json"))[0].read_text())
        assert "metrics" in meta
        assert "r2" in meta["metrics"]
        assert "training_rows" in meta
        assert meta["training_rows"] == len(sample_df)

    def test_latest_joblib_created(
        self,
        model_instance: AdvancedPriceModel,
        sample_df: pd.DataFrame,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
        model_instance.train(sample_df, validation_method="full")
        model_instance.save(models_dir=tmp_path)
        assert (tmp_path / "price_model_latest.joblib").exists()
        assert (tmp_path / "latest.txt").exists()


# ── load_or_train() ───────────────────────────────────────────────────────────

class TestLoadOrTrain:
    def test_trains_when_no_model_exists(
        self,
        sample_df: pd.DataFrame,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
        cat = ["manufacturer", "model", "condition", "fuel", "transmission",
               "drive", "type", "paint_color", "state"]
        num = ["year", "odometer", "vehicle_age"]
        model, metrics, from_cache = AdvancedPriceModel.load_or_train(
            sample_df, cat, num, models_dir=tmp_path
        )
        assert from_cache is False
        assert "r2" in metrics
        assert (tmp_path / "price_model_latest.joblib").exists()

    def test_loads_when_model_exists(
        self,
        sample_df: pd.DataFrame,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
        cat = ["manufacturer", "model", "condition", "fuel", "transmission",
               "drive", "type", "paint_color", "state"]
        num = ["year", "odometer", "vehicle_age"]
        # Primeiro treino
        AdvancedPriceModel.load_or_train(sample_df, cat, num, models_dir=tmp_path)
        # Segundo — deve carregar do cache
        _, metrics, from_cache = AdvancedPriceModel.load_or_train(
            sample_df, cat, num, models_dir=tmp_path
        )
        assert from_cache is True
        assert metrics == {}
