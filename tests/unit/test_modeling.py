import numpy as np
import pandas as pd

from geo_pulse.features.builder import build_features
from geo_pulse.modeling.mixed_effects import FittedModel, fit_group_fixed_effects
from geo_pulse.modeling.predictor import add_predictions
from geo_pulse.modeling.trainer import train_model
from geo_pulse.pipelines.modeling_pipeline import run_modeling_pipeline


def test_mixed_effects_model_runs(sample_paths, test_settings):
    properties = pd.read_csv(sample_paths[0])
    amenities = pd.read_csv(sample_paths[1])
    features, _ = build_features(properties, amenities, ["park"], 1000)
    effects = ["square_feet", "beds", "baths", "property_age", "dist_to_park_m"]
    predictions, _, summary = run_modeling_pipeline(
        features, "price", "neighborhood", effects, test_settings.models
    )
    assert summary.row_count == len(properties)
    assert summary.group_count == 4
    assert predictions["predicted_price"].gt(0).all()


def test_singular_random_effect_covariance_uses_fixed_predictions():
    class SingularResult:
        @property
        def fittedvalues(self):
            raise ValueError("Cannot predict random effects from singular covariance structure.")

        def predict(self, data):
            return data["log_price"] - 0.1

    data = pd.DataFrame({"log_price": [12.0, 13.0], "price": [162755.0, 442413.0]})
    fitted = FittedModel(
        result=SingularResult(),
        formula="log_price ~ square_feet",
        target="log_price",
        group_column="neighborhood",
        fixed_effects=["square_feet"],
        converged=True,
        warnings=[],
    )
    predictions = add_predictions(data, fitted, "price")
    assert fitted.fixed_only_prediction is True
    assert predictions["predicted_log_price"].tolist() == [11.9, 12.9]
    assert any("zero boundary" in warning for warning in fitted.warnings)


def test_group_fixed_effect_fallback_produces_stable_predictions(monkeypatch):
    groups = np.repeat(["A", "B", "C", "D"], 10)
    square_feet = np.tile(np.linspace(1000, 2000, 10), 4)
    group_effect = pd.Series(groups).map({"A": 0.0, "B": 0.2, "C": -0.1, "D": 0.1}).to_numpy()
    log_price = 11.0 + 0.0005 * square_feet + group_effect
    data = pd.DataFrame(
        {
            "neighborhood": groups,
            "square_feet": square_feet,
            "log_price": log_price,
            "price": np.exp(log_price),
        }
    )

    def fallback(frame, target, group_column, fixed_effects):
        return fit_group_fixed_effects(frame, target, group_column, fixed_effects)

    monkeypatch.setattr("geo_pulse.modeling.trainer.fit_mixed_effects", fallback)
    fitted, predictions, summary = train_model(
        data, "log_price", "price", "neighborhood", ["square_feet"]
    )
    assert fitted.is_mixed is False
    assert summary.model_type.startswith("OLS with geographic fixed effects")
    assert summary.metrics["r_squared"] > 0.99
    assert set(summary.random_effects) == {"A", "B", "C", "D"}
    assert predictions["predicted_price"].gt(0).all()
