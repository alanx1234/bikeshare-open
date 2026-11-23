"""Splits must be temporal, disjoint, and non-empty."""
import pandas as pd
import pytest

from src.config import TRAIN_END, VALID_END
from src.features import build_features
from src.ingest import load_raw
from src.train import temporal_split


@pytest.fixture(scope="module")
def splits():
    return temporal_split(build_features(load_raw()))


def test_splits_non_empty(splits):
    for part in splits:
        assert len(part) > 0


def test_splits_are_ordered_in_time(splits):
    train, valid, test = splits
    assert train.dteday.max() < valid.dteday.min()
    assert valid.dteday.max() < test.dteday.min()


def test_no_overlapping_dates(splits):
    train, valid, test = splits
    dates = pd.concat([train.dteday, valid.dteday, test.dteday])
    assert dates.is_unique


def test_residual_experiment_never_sees_the_test_set():
    """The Exercise 4 experiment is validation-only. Dropping every test-period
    row must not change a single number, and no test score may be reported."""
    from src.train import residual_experiment

    df = build_features(load_raw())
    full = residual_experiment(df)
    no_test = residual_experiment(df[df.dteday <= VALID_END])
    assert full == no_test
    assert full["split"] == "valid"
    assert "test" not in str(full)


def test_residual_experiment_baselines_match_hand_computation():
    """Scores are on the original count scale: persistence MAE is the mean
    absolute cnt - cnt_lag_1 over the validation rows."""
    from src.train import residual_experiment

    df = build_features(load_raw())
    _, valid, _ = temporal_split(df)
    res = residual_experiment(df)
    expected = (valid.cnt - valid.cnt_lag_1).abs().mean()
    assert res["baseline_persistence"]["mae"] == pytest.approx(expected, abs=0.05)
    assert res["n_valid"] == len(valid)


def test_paired_mae_gap_is_seeded_and_signed():
    """The Exercise 5 bootstrap must give identical intervals on every run,
    and a negative gap must mean the first model is better."""
    import numpy as np

    from src.train import paired_mae_gap

    rng = np.random.default_rng(1)
    y = rng.normal(5000, 1000, 182)
    good, bad = y + rng.normal(0, 100, 182), y + rng.normal(0, 800, 182)
    first, again = paired_mae_gap(y, good, bad), paired_mae_gap(y, good, bad)
    assert first == again
    assert first["mae_gap"] < 0
    assert first["ci95"][0] <= first["mae_gap"] <= first["ci95"][1]


def test_weather_ablation_reports_both_baselines():
    """CLAUDE.md: the mean AND persistence baselines go next to every model
    score. The ablation's validation block must carry both, matching the
    residual experiment's independently fitted baselines."""
    from src.train import residual_experiment, weather_ablation

    raw = load_raw()
    df = build_features(raw)
    abl = weather_ablation(df, raw, include_test=False)  # pytest never scores test
    res = residual_experiment(df)
    assert "test_descriptive" not in abl
    for base in ("baseline_mean", "baseline_persistence"):
        assert abl["valid"][base] == res[base]
