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
Optional experiments, which print results and write no files:
  python -m src.train --residual-experiment   (Exercise 4, validation only)
  python -m src.train --weather-ablation      (Exercise 5)
"""
import argparse
import json

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.config import (
    BOOTSTRAP_DRAWS,
    BOOTSTRAP_SEED,
    METRICS,
    PROCESSED,
    SAME_DAY_WEATHER_FEATURES,
    TARGET,
    TRAIN_END,
    VALID_END,
)
from src.features import feature_columns, previous_day_weather
from src.ingest import load_raw


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


def paired_mae_gap(y, pred_a, pred_b) -> dict:
    """MAE(a) - MAE(b), with a 95% paired-bootstrap interval over days.
    Negative means a is better. Each call starts its own generator from
    BOOTSTRAP_SEED, so an interval does not depend on call order."""
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    y = np.asarray(y, dtype=float)
    err_a = np.abs(y - np.asarray(pred_a, dtype=float))
    err_b = np.abs(y - np.asarray(pred_b, dtype=float))
    idx = rng.integers(0, len(y), size=(BOOTSTRAP_DRAWS, len(y)))
    gaps = err_a[idx].mean(axis=1) - err_b[idx].mean(axis=1)
    lo, hi = np.percentile(gaps, [2.5, 97.5])
    return {
        "mae_gap": round(float(err_a.mean() - err_b.mean()), 1),
        "ci95": [round(float(lo), 1), round(float(hi), 1)],
    }


def weather_ablation(df: pd.DataFrame | None = None, raw: pd.DataFrame | None = None) -> dict:
    """Exercise 5: what same-day observed weather is worth to ridge.

    Validation (the only basis for any decision): ridge refit three ways --
    the default 15 features, same-day weather removed, and same-day weather
    replaced by the previous day's observation -- reported next to BOTH
    baselines (mean and persistence), with a paired bootstrap of each
    variant's MAE gap to persistence.

    Test (`test_descriptive`): descriptive only, never used to choose a
    model. Only the default models already scored in reports/metrics.json
    (ridge and both baselines), the same bootstrap, the count of days ridge
    is closer, and Hurricane Sandy.

    Features, split and hyperparameters are unchanged: every model is a
    clone() of MODELS. Prints only; writes no files.

    Run: python -m src.train --weather-ablation
    """
    if df is None:
        df = pd.read_parquet(PROCESSED)
    if raw is None:
        raw = load_raw()
    cols = feature_columns(df)
    weather = [c for c in SAME_DAY_WEATHER_FEATURES if c in cols]
    no_weather = [c for c in cols if c not in SAME_DAY_WEATHER_FEATURES]

    prev = previous_day_weather(raw)
    prev_cols = [c for c in prev.columns if c != "dteday"]
    df = df.merge(prev, on="dteday", how="left", validate="one_to_one")
    if df[prev_cols].isna().any().any():
        raise ValueError("previous-day weather missing for a modelled row")
    train, valid, test = temporal_split(df)

    def fit(name: str, fc: list[str]):
        return clone(MODELS[name]).fit(train[fc], train[TARGET])

    def score(y, pred) -> dict:
        return {
            "r2": round(float(r2_score(y, pred)), 4),
            "mae": round(float(mean_absolute_error(y, pred)), 1),
        }

    persistence = fit("baseline_persistence", cols)
    persist_valid = persistence.predict(valid[cols])
    mean_baseline = fit("baseline_mean", cols)
    variants = {
        "ridge_same_day_weather": cols,
        "ridge_previous_day_weather": no_weather + prev_cols,
        "ridge_no_weather": no_weather,
    }
    valid_res = {"n_valid": len(valid)}
    for name, fc in variants.items():
        pred = fit("ridge", fc).predict(valid[fc])
        valid_res[name] = {
            "n_features": len(fc),
            **score(valid[TARGET], pred),
            "vs_persistence": paired_mae_gap(valid[TARGET], pred, persist_valid),
        }
    valid_res["baseline_persistence"] = score(valid[TARGET], persist_valid)
    valid_res["baseline_mean"] = score(valid[TARGET], mean_baseline.predict(valid[cols]))

    ridge = fit("ridge", cols)
    ridge_test = ridge.predict(test[cols])
    persist_test = persistence.predict(test[cols])
    y_test = test[TARGET].to_numpy(dtype=float)
    sandy = (test.dteday == pd.Timestamp("2012-10-29")).to_numpy()
    test_res = {
        "n_test": len(test),
        "ridge": score(y_test, ridge_test),
        "baseline_persistence": score(y_test, persist_test),
        "baseline_mean": score(y_test, mean_baseline.predict(test[cols])),
        "ridge_vs_persistence": paired_mae_gap(y_test, ridge_test, persist_test),
        "days_ridge_closer": int(
            (np.abs(y_test - ridge_test) < np.abs(y_test - persist_test)).sum()
        ),
        "sandy_2012_10_29": {
            "actual": int(y_test[sandy][0]),
            "ridge": round(float(ridge_test[sandy][0])),
            "baseline_persistence": round(float(persist_test[sandy][0])),
        },
    }
    coefs = pd.Series(ridge[-1].coef_, index=cols)
    return {
        "bootstrap": {"draws": BOOTSTRAP_DRAWS, "seed": BOOTSTRAP_SEED},
        "same_day_weather_features": weather,
        "valid": valid_res,
        "test_descriptive": test_res,
        "ridge_standardised_coefficients": {
            c: round(float(v), 1)
            for c, v in coefs.reindex(coefs.abs().sort_values(ascending=False).index).items()
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--residual-experiment",
        action="store_true",
        help="validation only: HGB on cnt - cnt_lag_1; prints, writes nothing",
    )
    parser.add_argument(
        "--weather-ablation",
        action="store_true",
        help="Exercise 5: ridge with/without same-day weather vs persistence, "
        "seeded bootstrap; prints, writes nothing",
    )
    args = parser.parse_args()

    if args.weather_ablation:
        res = weather_ablation()
        print(json.dumps(res, indent=2))
        v = res["valid"]
        print(
            "OK weather ablation (valid): ridge MAE gap vs persistence "
            f"{v['ridge_same_day_weather']['vs_persistence']['mae_gap']} with same-day weather, "
            f"{v['ridge_no_weather']['vs_persistence']['mae_gap']} without "
            f"(seed {res['bootstrap']['seed']}, {res['bootstrap']['draws']} draws)"
        )
    elif args.residual_experiment:
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
