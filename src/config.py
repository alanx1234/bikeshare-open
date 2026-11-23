"""Single source of truth for paths, columns, and split dates."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "bike_daily.csv"
PROCESSED = ROOT / "data" / "processed" / "features.parquet"
METRICS = ROOT / "reports" / "metrics.json"

# Daily Capital Bikeshare counts (Fanaee-T & Gama). Canonical home:
#   https://archive.ics.uci.edu/dataset/275/bike+sharing+dataset
# We use the processed copy from Molnar's "Interpretable Machine Learning"
# because the UCI host blocks some campus networks. It differs from UCI:
#   - 728 rows, 2011-01-03 to 2012-12-31 (UCI has 731 from 2011-01-01)
#   - 2011-03-10 is absent (the UCI row records humidity 0, a sensor
#     artefact, and the mirror's cleaning dropped the whole day)
#   - `weather` is the labels GOOD / MISTY / BAD, not UCI's codes 1-4
#   - two extra columns: `days_since_2011` and `cnt_2d_bfr`
DATA_URL = (
    "https://raw.githubusercontent.com/christophM/"
    "interpretable-ml-book/master/data/bike.csv"
)

# SHA-256 of the committed raw CSV. Permission rules only bind Claude's
# Edit/Write tools, and the PostToolUse hook only fires on those, so a `cp`
# from Bash can replace the file unseen. `make data` and
# tests/test_contract.py compare against this hash, so any change to the raw
# bytes, by any route, fails loudly (docs/SEEDED_FAULTS.md, fault 4).
RAW_SHA256 = "a6bed1577f6e4de56dcfae6d8315985073cc0ad3446c8c99ed60c86a0b5ad9dc"

TARGET = "cnt"

# --- Four reasons a column is kept out of the feature set ---------------

# 1. Leakage: the target or an arithmetic restatement of it.
#    casual + registered == cnt exactly, on every row. A model handed these
#    scores R^2 ~ 1.0 and has learned addition. At prediction time you would
#    not know either input: they are components of the thing being predicted.
LEAKAGE_COLS = {"casual", "registered", "cnt"}

# 2. Time indexes: not leakage, but a bad bet. A tree splits on "after date
#    X" and predicts a flat constant for every future date; a linear model
#    extrapolates a two-year trend we have no reason to trust. Excluding
#    them keeps the model comparison about what each does with lagged demand.
TIME_INDEX_COLS = {"instant", "yr", "days_since_2011"}

# 3. Unverified: `cnt_2d_bfr` is a two-day lag of cnt that shipped with the
#    mirror. It is NOT leakage -- a two-day-old count is known at prediction
#    time -- but we did not build it and cannot test how it was aligned, so we
#    build our own lags from the target and test those instead.
UNVERIFIED_COLS = {"cnt_2d_bfr"}

# 4. Redundant calendar: NOT leakage -- each is known in advance from the
#    date. They are text restatements of `dteday` (season and month names,
#    weekday abbreviations), and src/features.py already derives the same
#    information from `dteday` as dayofweek, month_sin and month_cos.
#    Listing them here records that they are excluded on purpose, rather
#    than dropped silently because they are not numeric.
REDUNDANT_CALENDAR_COLS = {"season", "mnth", "weekday"}

# What feature_columns() and the tests actually enforce.
FORBIDDEN = LEAKAGE_COLS | TIME_INDEX_COLS | UNVERIFIED_COLS | REDUNDANT_CALENDAR_COLS

# Raw columns the model may draw on: used directly (the numeric weather
# readings) or encoded into a feature in src/features.py (holiday, workday,
# weather). This is a classification of raw inputs, not the feature list:
# feature_columns() still derives that from FORBIDDEN. tests/test_contract.py
# fails if any raw CSV column is in neither set (and is not `dteday`), so a
# column added upstream cannot slip into, or out of, the model unreviewed.
RAW_FEATURE_COLS = {
    "temp", "atemp", "hum", "windspeed",
    "holiday", "workday", "weather",
}

# Same-day observed weather. NOT leakage, and kept in the default feature
# set, but these are measurements of the day being predicted: a day-ahead
# forecaster would only have a weather forecast. Scores that use them are
# nowcast scores. `python -m src.train --weather-ablation` measures what
# they are worth (REPORT.md, Exercise 5 and Limitations).
SAME_DAY_WEATHER_FEATURES = ["temp", "atemp", "hum", "windspeed", "weather_severity"]

# Paired bootstrap of the MAE gap in the weather-ablation experiment.
BOOTSTRAP_DRAWS = 5000
BOOTSTRAP_SEED = 0

# Temporal split: train on 2011, validate on H1 2012, test on H2 2012.
TRAIN_END = "2011-12-31"
VALID_END = "2012-06-30"

# Longest lag window in src/features.py. The first LAG_WARMUP calendar days
# have no complete history and are dropped; tests/test_contract.py uses this
# to bound how many rows may legitimately disappear.
LAG_WARMUP = 7
