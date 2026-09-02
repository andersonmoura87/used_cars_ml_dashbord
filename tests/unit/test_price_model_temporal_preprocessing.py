"""Regressões de isolamento do preprocessing na validação temporal."""

from unittest.mock import patch

import numpy as np
import pandas as pd

from src.models.price_model import AdvancedPriceModel


def _model() -> AdvancedPriceModel:
    return AdvancedPriceModel(["category"], ["value"])


def test_future_only_category_is_not_learned_and_uses_unknown_bucket():
    model = _model()
    train = pd.DataFrame({"category": ["A", "B"], "value": [1.0, 2.0]})
    validation = pd.DataFrame({"category": ["FUTURE_ONLY"], "value": [3.0]})
    state = model._fit_preprocessor(train)
    transformed = model._transform_with_preprocessor(validation, state)
    encoder = state.label_encoders["category"]
    assert "FUTURE_ONLY" not in encoder.classes_
    assert transformed.iloc[0]["category"] == encoder.transform(["__unknown__"])[0]


def test_fold_imputation_median_comes_only_from_training_data():
    model = _model()
    train = pd.DataFrame({"category": ["A"] * 4, "value": [1.0, 3.0, np.nan, np.nan]})
    validation = pd.DataFrame({"category": ["A"] * 2, "value": [1_000_000.0] * 2})
    state = model._fit_preprocessor(train)
    assert state.numeric_fill_values["value"] == 2.0
    assert pd.concat([train, validation])["value"].median() != 2.0


def test_fold_robust_scaler_statistics_come_only_from_training_data():
    model = _model()
    train = pd.DataFrame({"category": ["A"] * 4, "value": [0.0, 10.0, 20.0, 30.0]})
    validation = pd.DataFrame({"category": ["A"] * 2, "value": [1_000_000.0] * 2})
    state = model._fit_preprocessor(train)
    assert state.scaler.center_[0] == 15.0
    assert state.scaler.scale_[0] == 15.0
    assert np.median(pd.concat([train, validation])["value"]) != state.scaler.center_[0]


def test_temporal_training_fits_independent_preprocessor_per_fold():
    size = 18
    df = pd.DataFrame(
        {
            "category": ["A"] * 6 + ["B"] * 9 + ["FUTURE_ONLY"] * 3,
            "value": np.arange(size, dtype=float),
            "price": np.linspace(10_000.0, 20_000.0, size),
        }
    )
    model = _model()
    model.model.set_params(n_estimators=2, max_depth=1)
    with patch.object(model, "_emit_training_lineage"):
        model.train(df, validation_method="time_series")
    states = model._temporal_cv_preprocessors
    assert len(states) == 5
    assert len({id(state.scaler) for state in states}) == 5
    assert [state.numeric_fill_values["value"] for state in states] == [1.0, 2.5, 4.0, 5.5, 7.0]
    assert "B" not in states[0].label_encoders["category"].classes_
    assert "FUTURE_ONLY" not in states[-1].label_encoders["category"].classes_
