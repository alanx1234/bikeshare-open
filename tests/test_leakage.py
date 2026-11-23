"""The tests that make the agent honest.

test_no_forbidden_features is the single most valuable test in this repo:
casual + registered == cnt exactly, so any model handed those columns
scores R^2 = 1.0 and looks brilliant while having learned nothing.
"""
import csv
import datetime

import pandas as pd
import pytest

from src.config import FORBIDDEN, RAW, TARGET
from src.features import build_features, feature_columns
from src.ingest import load_raw


@pytest.fixture(scope="module")
def feats():
    return build_features(load_raw())


def test_leakage_identity_holds(feats):
    """Documents *why* casual and registered are forbidden."""
    assert (feats.casual + feats.registered == feats[TARGET]).all()


def test_no_forbidden_features(feats):
    """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
    construction, so this cannot discover a *new* leaky column. What it
    catches is someone editing feature_columns() or FORBIDDEN -- which is
    exactly the fault the Step 7 hook demonstrates."""
    cols = set(feature_columns(feats))
    assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"


def test_lags_are_true_calendar_lags(feats):
    """cnt_lag_1 for date d must equal cnt on d-1, in calendar days."""
    by_date = feats.set_index("dteday")[TARGET]
    checked = 0
    for date, lag in feats.set_index("dteday").cnt_lag_1.items():
        prev = date - pd.Timedelta(days=1)
        if prev in by_date.index:
            assert lag == pytest.approx(by_date[prev]), f"bad lag at {date.date()}"
            checked += 1
    assert checked > 600, "too few rows actually verified"


def test_lag_is_not_the_target(feats):
    assert not (feats.cnt_lag_1 == feats[TARGET]).all()


def _raw_counts_by_date() -> dict[str, int]:
    """cnt by ISO date, read with the csv module straight from the raw file,
    so the expected values do not depend on load_raw(), pandas rolling, or
    build_features() -- the code under test."""
    with open(RAW, newline="") as fh:
        return {row["dteday"]: int(row[TARGET]) for row in csv.DictReader(fh)}


# Each date is chosen for a reason; the reason is printed on failure.
ROLLING_MEAN_DATES = {
    "2011-01-10": "first modelled day: its window is the first 7 rows of the file",
    "2011-03-18": "first day whose window sits right after the missing 2011-03-10",
    "2011-06-15": "ordinary mid-year day",
    "2012-01-01": "window crosses the year boundary from train into validation",
    "2012-03-01": "window includes the leap day 2012-02-29",
    "2012-10-30": "window includes Hurricane Sandy (2012-10-29, 22 rides)",
}


@pytest.mark.parametrize("date", sorted(ROLLING_MEAN_DATES))
def test_rolling_mean_excludes_today(feats, date):
    """cnt_roll_7 on date d must be the plain mean of cnt on d-7 .. d-1, in
    calendar days. Fails, rather than skips, if a window is incomplete."""
    counts = _raw_counts_by_date()
    day = datetime.date.fromisoformat(date)
    window = [(day - datetime.timedelta(days=k)).isoformat() for k in range(1, 8)]
    missing = [d for d in window if d not in counts]
    assert not missing, f"{date}: window incomplete, missing {missing}"
    expected = sum(counts[d] for d in window) / 7

    got = feats.set_index("dteday").cnt_roll_7.get(pd.Timestamp(date))
    assert got is not None, f"{date} is not in the feature table"
    assert got == pytest.approx(expected), f"{date}: {ROLLING_MEAN_DATES[date]}"


@pytest.mark.parametrize("date", ["2011-06-15", "2011-03-18"])
def test_rolling_std_excludes_today(feats, date):
    """cnt_std_7 must be the sample std (ddof=1) of the 7 calendar days
    *before* today. 2011-03-18 is the first row whose window sits right
    after the missing 2011-03-10, so a row-based window would be wrong.
    Window counts come from the raw data: dropna removes the rows right
    after the gap from `feats`, but their counts are real."""
    by_date = load_raw().set_index("dteday")[TARGET]
    date = pd.Timestamp(date)
    window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
    assert all(d in by_date.index for d in window), "window must be complete"
    expected = pd.Series([by_date[d] for d in window]).std(ddof=1)
    assert feats.set_index("dteday").cnt_std_7[date] == pytest.approx(expected)


def test_no_missing_values(feats):
    assert feats[feature_columns(feats)].isna().sum().sum() == 0


def test_dates_are_sorted_and_unique(feats):
    assert feats.dteday.is_monotonic_increasing
    assert feats.dteday.is_unique


@pytest.mark.parametrize(
    "date, source",
    [
        ("2011-03-12", "2011-03-11"),  # first day after the missing 2011-03-10 with a real d-1
        ("2012-03-01", "2012-02-29"),  # leap day
        ("2011-06-15", "2011-06-14"),
    ],
)
def test_previous_day_weather_is_yesterday(date, source):
    """Experiment-only feature (weather ablation): the value on d must be
    the raw observation from d-1 in calendar days, read independently with
    the csv module."""
    from src.features import WEATHER_ORDER, previous_day_weather

    with open(RAW, newline="") as fh:
        rows = {r["dteday"]: r for r in csv.DictReader(fh)}
    prev = previous_day_weather(load_raw()).set_index("dteday").loc[pd.Timestamp(date)]
    for col in ["temp", "atemp", "hum", "windspeed"]:
        assert prev[f"{col}_prev"] == pytest.approx(float(rows[source][col])), f"{date} {col}"
    assert prev["weather_severity_prev"] == WEATHER_ORDER[rows[source]["weather"]]


def test_previous_day_weather_is_missing_after_the_gap():
    """2011-03-11's yesterday is the absent 2011-03-10: NaN, not 03-09."""
    from src.features import previous_day_weather

    prev = previous_day_weather(load_raw()).set_index("dteday")
    assert prev.loc[pd.Timestamp("2011-03-11")].isna().all()
