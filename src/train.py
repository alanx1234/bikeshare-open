"""Stage 3: temporal split, fit, evaluate, write metrics.

Two baselines and two models, on purpose.

  baseline_mean         predict the 2011 average for every day
  baseline_persistence  predict yesterday's count (cnt_lag_1)
  ridge                 standardised linear model on the audited features
  hgb                   gradient-boosted trees on the same features

The mean baseline shows what "the distribution moved" costs. Persistence
is the baseline that actually matters: ridge's features are dominated by
lagged demand, so if it cannot beat "yesterday again" it has learned
nothing worth reporting. The booster is there because it fails, and the
reason it fails is the headline result.

Run: python -m src.train
"""
import argparse
import json

import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.config import METRICS, PROCESSED, TARGET, TRAIN_END, VALID_END
from src.features import feature_columns


class PersistenceBaseline(BaseEstimator, RegressorMixin):
    """Predict a single lagged column unchanged. Nothing is fit."""

    def __init__(self, column: str = "cnt_lag_1"):
        self.column = column

    def fit(self, X, y=None):
        if self.column not in X.columns:
            raise ValueError(f"persistence baseline needs column {self.column!r}")
        return self

    def predict(self, X):
        return X[self.column].to_numpy(dtype=float)


MODELS = {
    "baseline_mean": DummyRegressor(strategy="mean"),
    "baseline_persistence": PersistenceBaseline("cnt_lag_1"),
    "ridge": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
    "hgb": HistGradientBoostingRegressor(random_state=0, max_iter=300),
}


def temporal_split(df: pd.DataFrame):
    """Split by date, never at random. A random split on a time series
    puts tomorrow in train and today in test."""
    train = df[df.dteday <= TRAIN_END]
    valid = df[(df.dteday > TRAIN_END) & (df.dteday <= VALID_END)]
    test = df[df.dteday > VALID_END]
    return train, valid, test


def fit_and_score() -> dict:
    df = pd.read_parquet(PROCESSED)
    cols = feature_columns(df)
    train, valid, test = temporal_split(df)

    results = {
        "n_features": len(cols),
        "features": cols,
        "n_train": len(train),
        "n_valid": len(valid),
        "n_test": len(test),
    }
    for name, model in MODELS.items():
        model.fit(train[cols], train[TARGET])
        results[name] = {
            split: {
                "r2": round(float(r2_score(part[TARGET], model.predict(part[cols]))), 4),
                "mae": round(float(mean_absolute_error(part[TARGET], model.predict(part[cols]))), 1),
            }
            for split, part in [("valid", valid), ("test", test)]
        }
    return results


RESIDUAL_BASE = "cnt_lag_1"


def residual_experiment(df: pd.DataFrame | None = None) -> dict:
    """Optional, validation-only experiment: train HGB on the day-over-day
    change (cnt - cnt_lag_1) and add cnt_lag_1 back to its predictions.

    Trees cannot predict outside the target range they saw in 2011, and
    2012 is ~65% busier. Predicting the change instead of the level lets
    cnt_lag_1 carry the level. Features, split and hyperparameters are the
    same as fit_and_score(): every model is a clone() of MODELS. cnt_lag_1
    is yesterday's count, so it is known when today is predicted. Every
    score is on the original count scale.

    The test split is never scored and nothing is written to disk, so
    reports/metrics.json is untouched.

    Run: python -m src.train --residual-experiment
    """
    if df is None:
        df = pd.read_parquet(PROCESSED)
    cols = feature_columns(df)
    if RESIDUAL_BASE not in cols:
        raise ValueError(f"residual experiment needs feature {RESIDUAL_BASE!r}")
    train, valid, _ = temporal_split(df)  # test set deliberately unused

    def score(pred) -> dict:
        return {
            "r2": round(float(r2_score(valid[TARGET], pred)), 4),
            "mae": round(float(mean_absolute_error(valid[TARGET], pred)), 1),
        }

    results = {"split": "valid", "n_train": len(train), "n_valid": len(valid)}
    for name, model in MODELS.items():
        fitted = clone(model).fit(train[cols], train[TARGET])
        results[name] = score(fitted.predict(valid[cols]))

    delta = train[TARGET] - train[RESIDUAL_BASE]
    hgb_delta = clone(MODELS["hgb"]).fit(train[cols], delta)
    results["hgb_residual"] = score(
        hgb_delta.predict(valid[cols]) + valid[RESIDUAL_BASE].to_numpy(dtype=float)
    )
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--residual-experiment",
        action="store_true",
        help="validation only: HGB on cnt - cnt_lag_1; prints, writes nothing",
    )
    args = parser.parse_args()

    if args.residual_experiment:
        res = residual_experiment()
        print(json.dumps(res, indent=2))
        print(
            f"OK residual experiment (valid only): hgb r2 {res['hgb']['r2']} -> "
            f"hgb_residual r2 {res['hgb_residual']['r2']}"
        )
    else:
        res = fit_and_score()
        METRICS.parent.mkdir(parents=True, exist_ok=True)
        METRICS.write_text(json.dumps(res, indent=2))
        print(json.dumps({k: v for k, v in res.items() if k != "features"}, indent=2))
