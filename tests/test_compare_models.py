"""
Testes unitários para scripts/compare_models.py.

Verifica a lógica de champion/challenger sem precisar de servidor MLflow.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.compare_models import (
    ModelMetrics,
    _challenger_wins,
    compare,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_metrics(
    version: str = "1",
    stage: str = "Production",
    r2: float | None = 0.85,
    rmse: float | None = 3000.0,
    mae: float | None = 2000.0,
) -> ModelMetrics:
    return ModelMetrics(
        version=version,
        stage=stage,
        run_id=f"run_{version}",
        r2=r2,
        rmse=rmse,
        mae=mae,
        registered_at="2026-01-01 00:00 UTC",
    )


# ── _challenger_wins() ────────────────────────────────────────────────────────

class TestChallengerWins:
    def test_challenger_wins_better_r2(self):
        champion   = _make_metrics(r2=0.85, rmse=3000)
        challenger = _make_metrics(version="2", stage="Staging", r2=0.86, rmse=2900)
        wins, reasons = _challenger_wins(champion, challenger, min_improvement=0.001)
        assert wins is True
        assert any("R²" in r for r in reasons)

    def test_challenger_loses_worse_r2(self):
        champion   = _make_metrics(r2=0.85, rmse=3000)
        challenger = _make_metrics(version="2", stage="Staging", r2=0.84, rmse=2900)
        wins, reasons = _challenger_wins(champion, challenger, min_improvement=0.001)
        assert wins is False

    def test_challenger_loses_r2_below_min_improvement(self):
        """Melhoria de 0.0001 não passa com min_improvement=0.001."""
        champion   = _make_metrics(r2=0.8500, rmse=3000)
        challenger = _make_metrics(version="2", stage="Staging", r2=0.8501, rmse=3000)
        wins, reasons = _challenger_wins(champion, challenger, min_improvement=0.001)
        assert wins is False

    def test_challenger_wins_r2_exactly_min_improvement(self):
        champion   = _make_metrics(r2=0.850, rmse=3000)
        challenger = _make_metrics(version="2", stage="Staging", r2=0.851, rmse=3000)
        wins, reasons = _challenger_wins(champion, challenger, min_improvement=0.001)
        assert wins is True

    def test_challenger_loses_rmse_regression_above_5pct(self):
        """RMSE piora mais de 5% → challenger perde mesmo com R² melhor."""
        champion   = _make_metrics(r2=0.85, rmse=3000)
        challenger = _make_metrics(version="2", stage="Staging", r2=0.86, rmse=3200)
        wins, reasons = _challenger_wins(champion, challenger, min_improvement=0.001)
        assert wins is False
        assert any("5%" in r or "REPROVADO" in r for r in reasons)

    def test_challenger_allowed_small_rmse_regression(self):
        """RMSE piora 3% → dentro da tolerância → challenger pode vencer se R² melhora."""
        champion   = _make_metrics(r2=0.85, rmse=3000)
        challenger = _make_metrics(version="2", stage="Staging", r2=0.86, rmse=3090)
        wins, reasons = _challenger_wins(champion, challenger, min_improvement=0.001)
        assert wins is True

    def test_champion_no_r2_challenger_has_r2(self):
        """Champion sem R² → challenger vence por bootstrap."""
        champion   = _make_metrics(r2=None, rmse=3000)
        challenger = _make_metrics(version="2", stage="Staging", r2=0.85, rmse=2900)
        wins, reasons = _challenger_wins(champion, challenger, min_improvement=0.001)
        assert wins is True

    def test_zero_min_improvement_always_needs_improvement(self):
        """Com min_improvement=0, qualquer melhoria (>=0) deve vencer."""
        champion   = _make_metrics(r2=0.85, rmse=3000)
        challenger = _make_metrics(version="2", stage="Staging", r2=0.85, rmse=3000)
        wins, _ = _challenger_wins(champion, challenger, min_improvement=0.0)
        assert wins is True  # delta=0 >= 0


# ── compare() — com client mockado ───────────────────────────────────────────

class TestCompareFunction:
    def _make_client(
        self,
        champion_r2: float | None = 0.85,
        champion_rmse: float = 3000,
        challenger_r2: float = 0.86,
        challenger_rmse: float = 2900,
    ) -> MagicMock:
        client = MagicMock()

        # Production (champion)
        champ_ver = MagicMock()
        champ_ver.version = "3"
        champ_ver.current_stage = "Production"
        champ_ver.run_id = "run_champ"
        champ_ver.creation_timestamp = 1700000000000
        champ_ver.tags = {}
        client.get_latest_versions.side_effect = lambda name, stages: (
            [champ_ver] if "Production" in stages else []
        )

        # Staging (challenger)
        chal_ver = MagicMock()
        chal_ver.version = "4"
        chal_ver.current_stage = "Staging"
        chal_ver.run_id = "run_chal"
        chal_ver.creation_timestamp = 1700001000000
        chal_ver.tags = {}
        # side_effect deve retornar challenger quando stage é Staging
        client.get_latest_versions.side_effect = lambda name, stages: (
            [champ_ver] if "Production" in stages else [chal_ver]
        )

        # Runs
        def get_run(run_id):
            run = MagicMock()
            if run_id == "run_champ":
                run.data.metrics = {"r2": champion_r2, "rmse": champion_rmse, "mae": 2000}
            else:
                run.data.metrics = {"r2": challenger_r2, "rmse": challenger_rmse, "mae": 1800}
            return run

        client.get_run.side_effect = get_run
        return client

    def test_compare_challenger_wins_returns_true(self, tmp_path: Path):
        client = self._make_client(champion_r2=0.85, challenger_r2=0.86)
        result = compare(
            client=client,
            model_name="test_model",
            challenger_version=None,
            min_improvement=0.001,
            dry_run=False,
            output_json=str(tmp_path / "result.json"),
        )
        assert result is True
        data = json.loads((tmp_path / "result.json").read_text())
        assert data["challenger_wins"] is True
        assert data["challenger"]["version"] == "4"
        assert data["champion"]["version"] == "3"

    def test_compare_champion_wins_returns_false(self, tmp_path: Path):
        client = self._make_client(champion_r2=0.90, challenger_r2=0.85)
        result = compare(
            client=client,
            model_name="test_model",
            challenger_version=None,
            min_improvement=0.001,
            dry_run=False,
            output_json=str(tmp_path / "result.json"),
        )
        assert result is False
        data = json.loads((tmp_path / "result.json").read_text())
        assert data["challenger_wins"] is False

    def test_compare_no_champion_bootstrap(self, tmp_path: Path):
        """Sem champion em Production → challenger vence automaticamente."""
        client = MagicMock()
        client.get_latest_versions.return_value = []

        chal_ver = MagicMock()
        chal_ver.version = "1"
        chal_ver.current_stage = "None"
        chal_ver.run_id = "run_1"
        chal_ver.creation_timestamp = 1700000000000
        chal_ver.tags = {}
        client.search_model_versions.return_value = [chal_ver]

        run = MagicMock()
        run.data.metrics = {"r2": 0.82, "rmse": 3500, "mae": 2200}
        client.get_run.return_value = run

        result = compare(
            client=client,
            model_name="test_model",
            challenger_version=None,
            min_improvement=0.001,
            dry_run=False,
            output_json=str(tmp_path / "result.json"),
        )
        assert result is True
        data = json.loads((tmp_path / "result.json").read_text())
        assert data["champion"]["version"] is None

    def test_compare_outputs_json(self, tmp_path: Path):
        client = self._make_client()
        output = tmp_path / "out.json"
        compare(
            client=client,
            model_name="test_model",
            challenger_version=None,
            min_improvement=0.001,
            dry_run=False,
            output_json=str(output),
        )
        assert output.exists()
        data = json.loads(output.read_text())
        assert "challenger_wins" in data
        assert "reasons" in data
        assert "evaluated_at" in data

    def test_compare_dry_run_still_returns_result(self, tmp_path: Path):
        """dry_run não altera o resultado — só evita exit(1)."""
        client = self._make_client(champion_r2=0.90, challenger_r2=0.85)
        result = compare(
            client=client,
            model_name="test_model",
            challenger_version=None,
            min_improvement=0.001,
            dry_run=True,
            output_json=None,
        )
        assert result is False  # challenger ainda perde, mas dry_run não chamaria exit(1)

    def test_github_output_written(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """GITHUB_OUTPUT deve receber challenger_wins e challenger_version."""
        output_file = tmp_path / "github_output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        client = self._make_client(champion_r2=0.85, challenger_r2=0.86)
        compare(
            client=client,
            model_name="test_model",
            challenger_version=None,
            min_improvement=0.001,
            dry_run=False,
            output_json=None,
        )
        content = output_file.read_text()
        assert "challenger_wins=true" in content
        assert "challenger_version=4" in content
