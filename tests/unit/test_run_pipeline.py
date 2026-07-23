"""
Testes unitários — src.etl.run_pipeline (orquestração com mocks).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.etl.run_pipeline import run_pipeline, save_metadata


def _fake_extract():
    df = pd.DataFrame({"price": [1], "year": [2020]})
    return df, {"total_records": 1}


def _fake_transform(df):
    clean = df.copy()
    removed = pd.DataFrame()
    stats = pd.DataFrame({"manufacturer": ["toyota"], "avg_price": [1.0]})
    meta = {"input_records": 1, "output_records": 1, "removed_records": 0}
    return clean, removed, stats, meta


class TestSaveMetadata:
    def test_writes_json(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        save_metadata({"ok": True, "n": 1}, "extract")
        files = list((tmp_path / "logs" / "metadata").glob("extract_*.json"))
        assert len(files) == 1
        assert "ok" in files[0].read_text(encoding="utf-8")


class TestRunPipeline:
    def test_happy_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_lineage = MagicMock()
        mock_lineage.start.return_value = "run-123"

        with patch("src.etl.run_pipeline.test_connection", return_value=True), \
             patch("src.etl.run_pipeline.extract_data", side_effect=_fake_extract), \
             patch("src.etl.run_pipeline.validate_raw", return_value=True), \
             patch("src.etl.run_pipeline.transform_data", side_effect=_fake_transform), \
             patch("src.etl.run_pipeline.validate_clean", return_value=True), \
             patch("src.etl.run_pipeline.load_data", return_value={"ok": True}), \
             patch("src.etl.run_pipeline.LineageClient", return_value=mock_lineage):

            assert run_pipeline() is True

        mock_lineage.start.assert_called_once()
        mock_lineage.complete.assert_called_once()
        mock_lineage.fail.assert_not_called()

        pipeline_metas = list((tmp_path / "logs" / "metadata").glob("pipeline_*.json"))
        assert len(pipeline_metas) == 1

    def test_db_connection_failure(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_lineage = MagicMock()
        mock_lineage.start.return_value = "run-fail"

        with patch("src.etl.run_pipeline.test_connection", return_value=False), \
             patch("src.etl.run_pipeline.LineageClient", return_value=mock_lineage):

            assert run_pipeline() is False

        mock_lineage.fail.assert_called_once()
        mock_lineage.complete.assert_not_called()

    def test_ge_clean_failure(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mock_lineage = MagicMock()
        mock_lineage.start.return_value = "run-ge"

        with patch("src.etl.run_pipeline.test_connection", return_value=True), \
             patch("src.etl.run_pipeline.extract_data", side_effect=_fake_extract), \
             patch("src.etl.run_pipeline.validate_raw", return_value=True), \
             patch("src.etl.run_pipeline.transform_data", side_effect=_fake_transform), \
             patch("src.etl.run_pipeline.validate_clean",
                   side_effect=ValueError("GE clean failed")), \
             patch("src.etl.run_pipeline.LineageClient", return_value=mock_lineage):

            assert run_pipeline() is False

        mock_lineage.fail.assert_called_once()
        assert "GE clean failed" in str(mock_lineage.fail.call_args)
