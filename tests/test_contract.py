"""Guard rails on the ingest contract and the trained model's behaviour."""
import pandas as pd
import pytest
from sklearn.base import clone
from sklearn.metrics import r2_score

from src.config import FORBIDDEN, LAG_WARMUP, RAW, RAW_FEATURE_COLS, TARGET
from src.features import build_features, encode_weather, feature_columns, reindex_to_calendar
from src.ingest import load_raw
from src.train import MODELS, temporal_split


@pytest.fixture(scope="module")
def raw():
    return load_raw().sort_values("dteday").reset_index(drop=True)


@pytest.fixture(scope="module")
def feats(raw):
    return build_features(raw)


def test_every_raw_column_is_classified():
    """Every column in the raw CSV must be forbidden, a feature input, or
    `dteday`. feature_columns() works by exclusion, so an unclassified
    numeric column becomes a feature silently and an unclassified text
    column is dropped silently. Reads the CSV header itself, not load_raw(),
    so nothing upstream can hide a column."""
    assert not (FORBIDDEN & RAW_FEATURE_COLS), (
        f"classified as both forbidden and feature: {sorted(FORBIDDEN & RAW_FEATURE_COLS)}"
    )
    header = set(pd.read_csv(RAW, nrows=0).columns)
    unclassified = header - FORBIDDEN - RAW_FEATURE_COLS - {"dteday"}
    assert not unclassified, (
        f"raw columns not classified in src/config.py: {sorted(unclassified)}"
    )


def test_unknown_weather_label_raises():
    """An unmapped label must raise, not become NaN that dropna() deletes
    silently. NaN itself (the reindexed missing day) is allowed through."""
    ok = encode_weather(pd.Series(["GOOD", "MISTY", "BAD", None]))
    assert ok.iloc[:3].tolist() == [0.0, 1.0, 2.0]
    with pytest.raises(ValueError, match="unmapped weather labels"):
        encode_weather(pd.Series(["GOOD", "Bad"]))


def test_calendar_is_complete_before_lagging(raw):
    """The reindexed frame must have no gaps, or the lags are wrong."""
    grid = reindex_to_calendar(raw)
    assert set(grid.dteday.diff().dropna().dt.days.unique()) == {1}


def test_only_expected_rows_are_dropped(raw, feats):
    """Rows may only vanish for the lag warm-up or downstream of a genuinely
    absent day -- never because an encoder produced a silent NaN.

    Accounting: the first LAG_WARMUP days have no complete history. Each
    absent calendar day m costs the LAG_WARMUP rows after it (cnt_lag_1 is
    NaN on m+1, cnt_roll_7 is NaN on m+1..m+7, cnt_lag_7 on m+7; their
    union is 7 rows). Day m itself was never in `raw`, so it is not a loss.
    The bound is exact for the current feature set; add a longer lag and
    LAG_WARMUP in src/config.py must grow with it.
    """
    full = pd.date_range(raw.dteday.min(), raw.dteday.max(), freq="D")
    missing_days = len(full) - len(raw)
    allowed_loss = LAG_WARMUP + LAG_WARMUP * missing_days
    lost = len(raw) - len(feats)
    assert lost <= allowed_loss, f"lost {lost} rows; expected at most {allowed_loss}"


@pytest.mark.parametrize("baseline", ["baseline_mean", "baseline_persistence"])
def test_beats_the_mean_baseline(feats, baseline):
    """A model that cannot beat the baselines is not a result.

    Scored on VALIDATION, against baselines fit here, never on test. Until
    2026-11-22 this test scored ridge on the H2-2012 test split against a
    fixed R^2 > 0.4 on every run (docs/DECISIONS.md records it). A pass/fail
    gate on test performance is an invitation to tune on test."""
    cols = feature_columns(feats)
    train, valid, _ = temporal_split(feats)
    ridge = clone(MODELS["ridge"]).fit(train[cols], train[TARGET])
    base = clone(MODELS[baseline]).fit(train[cols], train[TARGET])
    ridge_r2 = r2_score(valid[TARGET], ridge.predict(valid[cols]))
    base_r2 = r2_score(valid[TARGET], base.predict(valid[cols]))
    assert ridge_r2 > base_r2, f"ridge valid R^2 {ridge_r2:.4f} <= {baseline} {base_r2:.4f}"


def test_persistence_baseline_is_reported():
    """The baseline that matters for a lag-driven model is 'yesterday again'.
    It must be in the comparison, whatever its score."""
    assert "baseline_persistence" in MODELS
