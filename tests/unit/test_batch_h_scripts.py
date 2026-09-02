"""Regressões focadas dos scripts revisados no Batch H."""

import importlib
import sys
from unittest.mock import patch

import pandas as pd
import pytest

from scripts.analysis.statistical_analysis import CarStatsAnalyzer
from scripts.train_model import prepare_temporal_training_data


def _analyzer(df: pd.DataFrame, tmp_path) -> CarStatsAnalyzer:
    analyzer = CarStatsAnalyzer.__new__(CarStatsAnalyzer)
    analyzer.df = df
    analyzer.results_path = tmp_path
    return analyzer


def test_pearson_uses_only_aligned_non_null_pairs(tmp_path):
    analyzer = _analyzer(
        pd.DataFrame(
            {
                "price": [10.0, 9999.0, 30.0, None],
                "odometer": [100.0, None, 300.0, 50000.0],
            }
        ),
        tmp_path,
    )
    with patch("scripts.analysis.statistical_analysis.sns.regplot"), patch(
        "scripts.analysis.statistical_analysis.plt.savefig"
    ):
        result = analyzer.price_mileage_correlation()

    assert result["correlation"] == pytest.approx(1.0)


def test_pearson_rejects_fewer_than_two_valid_pairs(tmp_path):
    analyzer = _analyzer(
        pd.DataFrame({"price": [10.0, None], "odometer": [100.0, 200.0]}),
        tmp_path,
    )
    with pytest.raises(ValueError, match="duas observações pareadas"):
        analyzer.price_mileage_correlation()


def test_pearson_rejects_constant_inputs(tmp_path):
    analyzer = _analyzer(
        pd.DataFrame({"price": [10.0, 10.0], "odometer": [100.0, 200.0]}),
        tmp_path,
    )
    with pytest.raises(ValueError, match="não constantes"):
        analyzer.price_mileage_correlation()


def test_compare_models_imports_without_mlflow_and_fails_only_on_use():
    import scripts.compare_models as compare_models

    with patch.dict(sys.modules, {"mlflow": None}):
        module = importlib.reload(compare_models)
        with pytest.raises(RuntimeError, match="mlflow não instalado"):
            module._get_client()

    importlib.reload(compare_models)


def test_temporal_preparation_sorts_stably_and_keeps_rows_aligned(caplog):
    df = pd.DataFrame(
        {
            "posting_date": [
                "2024-01-03",
                "invalid",
                "2024-01-01",
                "2024-01-02",
                "2024-01-02",
                "2024-01-04",
                "2024-01-05",
            ],
            "price": [30, 999, 10, 20, 21, 40, 50],
            "row_id": [3, 999, 1, 2, 21, 4, 5],
        }
    )

    result = prepare_temporal_training_data(df)

    assert result["row_id"].tolist() == [1, 2, 21, 3, 4, 5]
    assert result["price"].tolist() == [10, 20, 21, 30, 40, 50]
    assert str(result["posting_date"].dtype) == "datetime64[ns, UTC]"
    assert "Descartando 1 de 7" in caplog.text


def test_temporal_preparation_requires_posting_date():
    with pytest.raises(ValueError, match="posting_date"):
        prepare_temporal_training_data(pd.DataFrame({"price": range(10)}))


def test_temporal_preparation_fails_when_too_few_valid_dates_remain():
    df = pd.DataFrame(
        {
            "posting_date": ["2024-01-01", "invalid", None, "2024-01-02"],
            "price": [1, 2, 3, 4],
        }
    )
    with pytest.raises(ValueError, match="restaram 2"):
        prepare_temporal_training_data(df)
