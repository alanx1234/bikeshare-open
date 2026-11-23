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
