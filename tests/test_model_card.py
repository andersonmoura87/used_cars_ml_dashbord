"""
Testes unitários para scripts/generate_model_card.py (UCM-25).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.generate_model_card import (
    ModelCardData,
    build_card_data,
    find_latest_meta,
    load_from_meta,
    main,
    parse_args,
    render_model_card,
    write_model_card,
    _fmt_metric,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_meta(tmp_path: Path) -> Path:
    meta = {
        "version": "20260716_120000",
        "saved_at": "20260716_120000",
        "categorical_features": ["manufacturer", "fuel"],
        "numerical_features": ["year", "odometer"],
        "target": "price",
        "feature_names": ["manufacturer", "fuel", "year", "odometer"],
        "model_params": {"n_estimators": 100, "max_depth": 6},
        "training_rows": 5000,
        "data_hash": "abc123def456",
        "metrics": {"r2": 0.87, "rmse": 3200.5, "mae": 2100.0, "mape": 0.12},
        "validation_method": "TimeSeriesSplit (5-fold)",
    }
    path = tmp_path / "price_model_20260716_120000_meta.json"
    path.write_text(json.dumps(meta), encoding="utf-8")
    return path


# ── Helpers ───────────────────────────────────────────────────────────────────

class TestFmtMetric:
    def test_none(self):
        assert _fmt_metric(None) == "N/A"

    def test_float(self):
        assert _fmt_metric(0.8765) == "0.8765"

    def test_decimals(self):
        assert _fmt_metric(3200.567, 2) == "3200.57"


# ── load_from_meta ────────────────────────────────────────────────────────────

class TestLoadFromMeta:
    def test_loads_all_fields(self, sample_meta):
        data = load_from_meta(sample_meta)
        assert data.version == "20260716_120000"
        assert data.r2 == 0.87
        assert data.rmse == 3200.5
        assert data.mae == 2100.0
        assert data.training_rows == 5000
        assert data.data_hash == "abc123def456"
        assert "manufacturer" in data.categorical_features
        assert "year" in data.numerical_features
        assert data.extra_metrics.get("mape") == 0.12

    def test_missing_metrics_ok(self, tmp_path):
        path = tmp_path / "empty_meta.json"
        path.write_text(json.dumps({"version": "1"}), encoding="utf-8")
        data = load_from_meta(path)
        assert data.r2 is None
        assert data.version == "1"


# ── render_model_card ─────────────────────────────────────────────────────────

class TestRenderModelCard:
    def test_contains_required_sections(self):
        data = ModelCardData(
            model_name="used_cars_price_model",
            version="3",
            stage="Production",
            r2=0.85,
            rmse=3000.0,
            mae=2000.0,
            categorical_features=["manufacturer"],
            numerical_features=["year"],
            training_rows=1000,
            data_hash="deadbeef",
        )
        md = render_model_card(data)
        assert "# Model Card: used_cars_price_model" in md
        assert "## Model Details" in md
        assert "## Intended Use" in md
        assert "## Training Data" in md
        assert "## Evaluation Metrics" in md
        assert "## Limitations" in md
        assert "## Ethical Considerations" in md
        assert "0.8500" in md
        assert "3000.00" in md
        assert "`manufacturer`" in md
        assert "deadbeef" in md

    def test_audit_section_when_promoted(self):
        data = ModelCardData(
            version="5",
            promoted_by="alice",
            promotion_reason="Challenger won weekly retrain",
        )
        md = render_model_card(data)
        assert "## Audit Trail" in md
        assert "@alice" in md
        assert "Challenger won weekly retrain" in md

    def test_no_audit_section_by_default(self):
        md = render_model_card(ModelCardData(version="1"))
        assert "## Audit Trail" not in md


# ── write_model_card ──────────────────────────────────────────────────────────

class TestWriteModelCard:
    def test_writes_latest(self, tmp_path):
        paths = write_model_card("# card\n", tmp_path, version="1", versioned=False)
        assert len(paths) == 1
        assert paths[0].name == "MODEL_CARD.md"
        assert paths[0].read_text(encoding="utf-8") == "# card\n"

    def test_writes_versioned_copy(self, tmp_path):
        paths = write_model_card("# card\n", tmp_path, version="42", versioned=True)
        assert len(paths) == 2
        assert any("MODEL_CARD_v42_" in p.name for p in paths)


# ── find_latest_meta ──────────────────────────────────────────────────────────

class TestFindLatestMeta:
    def test_none_when_missing_dir(self, tmp_path):
        assert find_latest_meta(tmp_path / "nope") is None

    def test_picks_newest(self, tmp_path):
        older = tmp_path / "a_meta.json"
        newer = tmp_path / "b_meta.json"
        older.write_text("{}")
        newer.write_text("{}")
        os.utime(older, (1_700_000_000, 1_700_000_000))
        os.utime(newer, (1_800_000_000, 1_800_000_000))
        assert find_latest_meta(tmp_path) == newer

    def test_empty_dir(self, tmp_path):
        assert find_latest_meta(tmp_path) is None


# ── build_card_data / CLI ─────────────────────────────────────────────────────

class TestBuildCardData:
    def test_from_meta_arg(self, sample_meta):
        args = parse_args(["--meta", str(sample_meta), "--git-sha", "abc"])
        data = build_card_data(args)
        assert data.version == "20260716_120000"
        assert data.git_sha == "abc"

    def test_missing_meta_raises(self, tmp_path):
        args = parse_args(["--meta", str(tmp_path / "missing.json")])
        with pytest.raises(FileNotFoundError):
            build_card_data(args)

    def test_promoted_by_overlay(self, sample_meta):
        args = parse_args([
            "--meta", str(sample_meta),
            "--promoted-by", "bob",
            "--promotion-reason", "manual promote",
        ])
        data = build_card_data(args)
        assert data.promoted_by == "bob"
        assert data.promotion_reason == "manual promote"


class TestMain:
    def test_stdout_mode(self, sample_meta, capsys):
        rc = main(["--meta", str(sample_meta), "--stdout"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Model Card" in out
        assert "0.8700" in out

    def test_writes_files(self, sample_meta, tmp_path):
        out_dir = tmp_path / "cards"
        rc = main([
            "--meta", str(sample_meta),
            "--output-dir", str(out_dir),
            "--no-versioned",
        ])
        assert rc == 0
        assert (out_dir / "MODEL_CARD.md").exists()

    def test_json_dump(self, sample_meta, tmp_path):
        out_dir = tmp_path / "cards"
        dump = tmp_path / "card.json"
        rc = main([
            "--meta", str(sample_meta),
            "--output-dir", str(out_dir),
            "--json-dump", str(dump),
            "--no-versioned",
        ])
        assert rc == 0
        payload = json.loads(dump.read_text(encoding="utf-8"))
        assert payload["version"] == "20260716_120000"
        assert payload["r2"] == 0.87

    def test_github_output(self, sample_meta, tmp_path, monkeypatch):
        gh_out = tmp_path / "github_output.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(gh_out))
        out_dir = tmp_path / "cards"
        rc = main([
            "--meta", str(sample_meta),
            "--output-dir", str(out_dir),
            "--no-versioned",
        ])
        assert rc == 0
        content = gh_out.read_text(encoding="utf-8")
        assert "card_path=" in content
        assert "model_version=20260716_120000" in content
        assert "r2=0.87" in content

    def test_fails_without_source(self, tmp_path, monkeypatch):
        monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
        # force find_latest_meta to look at empty dir via cwd isolation
        with patch("scripts.generate_model_card.find_latest_meta", return_value=None):
            rc = main(["--output-dir", str(tmp_path)])
        assert rc == 1
