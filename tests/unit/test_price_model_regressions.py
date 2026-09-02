"""Regressões de preparação e inferência do modelo de preços."""

import pandas as pd

from src.models.price_model import AdvancedPriceModel


def _training_data() -> pd.DataFrame:
    return pd.DataFrame({
        "manufacturer": ["toyota", "ford"] * 10,
        "year": list(range(2004, 2024)),
        "odometer": [200_000 - i * 8_000 for i in range(20)],
        "price": [5_000 + i * 1_500 for i in range(20)],
    })


def test_unknown_category_is_encoded_without_failure():
    model = AdvancedPriceModel(["manufacturer"], ["year", "odometer"])
    model.prepare_features(_training_data(), fit=True)

    result = model.prepare_features(pd.DataFrame({
        "manufacturer": ["new-brand"],
        "year": [2024],
        "odometer": [100],
    }))

    assert result.shape == (1, 3)


def test_prediction_default_returns_historical_uncertainty():
    model = AdvancedPriceModel(["manufacturer"], ["year", "odometer"])
    model.model.set_params(n_estimators=1, max_depth=1)
    model.train(_training_data(), validation_method="full")

    predictions, uncertainty = model.predict(pd.DataFrame({
        "manufacturer": ["new-brand"],
        "year": [2024],
        "odometer": [1_000],
        "price": [15_000],
    }))

    assert len(predictions) == 1
    assert uncertainty is not None
    assert len(uncertainty) == 1


def test_prediction_without_uncertainty_does_not_require_target_column():
    model = AdvancedPriceModel(["manufacturer"], ["year", "odometer"])
    model.model.set_params(n_estimators=1, max_depth=1)
    model.train(_training_data(), validation_method="full")

    predictions, uncertainty = model.predict(pd.DataFrame({
        "manufacturer": ["new-brand"],
        "year": [2024],
        "odometer": [1_000],
    }), return_std=False)

    assert len(predictions) == 1
    assert uncertainty is None
