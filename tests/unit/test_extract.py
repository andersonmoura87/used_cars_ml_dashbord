"""
Testes unitários — src.etl.extract (cobertura ETL core).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.etl.extract import extract_data, read_csv_data, validate_raw_data


REQUIRED_COLS = [
    "manufacturer", "model", "year", "price", "odometer",
    "fuel", "transmission", "state", "posting_date",
]


def _sample_df(n: int = 5) -> pd.DataFrame:
    return pd.DataFrame({
        "manufacturer": ["toyota"] * n,
        "model": ["corolla"] * n,
        "year": [2018] * n,
        "price": [15000.0] * n,
        "odometer": [50000] * n,
        "fuel": ["gas"] * n,
        "transmission": ["automatic"] * n,
        "state": ["ca"] * n,
        "posting_date": pd.to_datetime(["2024-01-01"] * n, utc=True),
    })


def _write_csv(path: Path, df: pd.DataFrame | None = None) -> Path:
    df = df if df is not None else _sample_df()
    # posting_date as string for CSV round-trip
    out = df.copy()
    out["posting_date"] = out["posting_date"].astype(str)
    out.to_csv(path, index=False)
    return path


class TestValidateRawData:
    def test_ok(self):
        assert validate_raw_data(_sample_df()) is True

    def test_missing_columns_raises(self):
        df = _sample_df().drop(columns=["fuel"])
        with pytest.raises(ValueError, match="Colunas obrigatórias"):
            validate_raw_data(df)

    def test_negative_price_warns(self, caplog):
        df = _sample_df()
        df.loc[0, "price"] = -100
        with caplog.at_level("WARNING"):
            assert validate_raw_data(df) is True
        assert "Preços negativos" in caplog.text


class TestReadCsvData:
    def test_reads_file(self, tmp_path, monkeypatch):
        csv_path = _write_csv(tmp_path / "cars.csv")
        monkeypatch.setenv("RAW_DATA_PATH", str(csv_path))
        df = read_csv_data()
        assert len(df) == 5
        assert set(REQUIRED_COLS).issubset(df.columns)

    def test_missing_path_raises(self, monkeypatch):
        monkeypatch.setenv("RAW_DATA_PATH", "/no/such/file.csv")
        with pytest.raises(Exception):
            read_csv_data()


class TestExtractData:
    def test_returns_df_and_metadata(self, tmp_path, monkeypatch):
        csv_path = _write_csv(tmp_path / "cars.csv")
        monkeypatch.setenv("RAW_DATA_PATH", str(csv_path))
        df, meta = extract_data()
        assert len(df) == 5
        assert meta["total_records"] == 5
        assert meta["source"] == str(csv_path)
        assert "columns" in meta
        assert "timestamp" in meta

    def test_propagates_validation_error(self, tmp_path, monkeypatch):
        bad = _sample_df().drop(columns=["state"])
        csv_path = _write_csv(tmp_path / "bad.csv", bad)
        monkeypatch.setenv("RAW_DATA_PATH", str(csv_path))
        with pytest.raises(ValueError):
            extract_data()
