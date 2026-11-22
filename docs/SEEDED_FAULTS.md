# Seeded faults

Tests that were written to fail before the code they check existed, with
the exact output of that failing run and why it failed.

## `cnt_std_7`: rolling 7-day standard deviation of demand

**Test:** `tests/test_leakage.py::test_rolling_std_excludes_today`,
parametrized over 2011-06-15 (an ordinary date) and 2011-03-18 (the first
date whose 7-day window ends right after the missing 2011-03-10).

**State when run:** test written, feature not yet added to
`src.features.build_features`. Command: `python -m pytest tests/ -q`
(`make test`; there is no `make` on this machine). Exit code 1.

**Why it failed:** `build_features` does not create a `cnt_std_7` column
yet, so `feats.set_index("dteday").cnt_std_7` raises
`AttributeError: 'DataFrame' object has no attribute 'cnt_std_7'`. That is
the right reason to fail. Both cases got past the line before it,
`assert all(d in by_date.index for d in window)`, which confirms the
hand-computed expected value could be built from 7 complete calendar days
before each date. So the test itself is sound, and only the feature is
missing. The other 14 tests still pass, so adding the test broke nothing
else.

**An earlier, wrong-reason failure (fixed before this run):** the first
draft looked up the window counts in `feats`. For 2011-03-18 that failed on
the window-completeness assert instead, because `dropna()` removes
2011-03-11 to 2011-03-17 from `feats` (their lags reach back to the
NaN-filled 2011-03-10), even though those days' counts are real. The fix
was to read the counts from `load_raw()`. The exact output of that run was
not kept.

### Exact output

```text
.........FF.....                                                         [100%]
================================== FAILURES ===================================
_________________ test_rolling_std_excludes_today[2011-06-15] _________________

feats =         dteday  instant  season  ...  cnt_lag_1 cnt_lag_7   cnt_roll_7
0   2011-01-10     10.0  WINTER  ...      822.0...    1787.0  1530.142857
713 2012-12-31    731.0  WINTER  ...     1796.0     920.0  1531.428571

[714 rows x 28 columns]
date = Timestamp('2011-06-15 00:00:00')

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
>       assert feats.set_index("dteday").cnt_std_7[date] == pytest.approx(expected)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests\test_leakage.py:72: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self =             instant  season      yr  ... cnt_lag_1 cnt_lag_7   cnt_roll_7
dteday                               ...    ... 1787.0  1530.142857
2012-12-31    731.0  WINTER  2012.0  ...    1796.0     920.0  1531.428571

[714 rows x 27 columns]
name = 'cnt_std_7'

    @final
    def __getattr__(self, name: str):
        """
        After regular attribute access, try looking up the name
        This allows simpler access to columns for interactive use.
        """
        # Note: obj.x will always call obj.__getattribute__('x') prior to
        # calling obj.__getattr__('x').
        if (
            name not in self._internal_names_set
            and name not in self._metadata
            and name not in self._accessors
            and self._info_axis._can_hold_identifiers_and_holds_name(name)
        ):
            return self[name]
>       return object.__getattribute__(self, name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: 'DataFrame' object has no attribute 'cnt_std_7'. Did you mean: 'cnt_lag_7'?

..\..\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\pandas\core\generic.py:6321: AttributeError
_________________ test_rolling_std_excludes_today[2011-03-18] _________________

feats =         dteday  instant  season  ...  cnt_lag_1 cnt_lag_7   cnt_roll_7
0   2011-01-10     10.0  WINTER  ...      822.0...    1787.0  1530.142857
713 2012-12-31    731.0  WINTER  ...     1796.0     920.0  1531.428571

[714 rows x 28 columns]
date = Timestamp('2011-03-18 00:00:00')

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
>       assert feats.set_index("dteday").cnt_std_7[date] == pytest.approx(expected)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

tests\test_leakage.py:72: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

self =             instant  season      yr  ... cnt_lag_1 cnt_lag_7   cnt_roll_7
dteday                               ...    ... 1787.0  1530.142857
2012-12-31    731.0  WINTER  2012.0  ...    1796.0     920.0  1531.428571

[714 rows x 27 columns]
name = 'cnt_std_7'

    @final
    def __getattr__(self, name: str):
        """
        After regular attribute access, try looking up the name
        This allows simpler access to columns for interactive use.
        """
        # Note: obj.x will always call obj.__getattribute__('x') prior to
        # calling obj.__getattr__('x').
        if (
            name not in self._internal_names_set
            and name not in self._metadata
            and name not in self._accessors
            and self._info_axis._can_hold_identifiers_and_holds_name(name)
        ):
            return self[name]
>       return object.__getattribute__(self, name)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: 'DataFrame' object has no attribute 'cnt_std_7'. Did you mean: 'cnt_lag_7'?

..\..\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\pandas\core\generic.py:6321: AttributeError
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_rolling_std_excludes_today[2011-06-15] - A...
FAILED tests/test_leakage.py::test_rolling_std_excludes_today[2011-03-18] - A...
2 failed, 14 passed in 1.82s
```

## Exercise 2: `casual` forced into `feature_columns`

**Purpose:** a deliberately seeded leak, to check that the leakage test
and the `.claude/hooks/check_leakage.sh` hook catch it.

### Exact change

`src/features.py`, in `feature_columns()`, made with the Edit tool:

```diff
-    return [c for c in numeric if c not in FORBIDDEN]
+    return [c for c in numeric if c not in FORBIDDEN] + ["casual"]  # EXERCISE 2: seeded leak
```

`casual` is in `FORBIDDEN` because `casual + registered == cnt` exactly on
every row. A model given it is being handed part of the answer.

### Why it failed

`test_no_forbidden_features` checks the list `feature_columns()` actually
returns against `FORBIDDEN`, so a column pushed past the filter is caught.
It guards the gate, not the data. It is the only test that failed; nothing
in `src/train.py` would have stopped `casual` from going into every model.

### Failing test output

Command: `python -m pytest tests/ -q`. Exit code 1.

```text
......F..........                                                        [100%]
================================== FAILURES ===================================
_________________________ test_no_forbidden_features __________________________

feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7    cnt_std_7
0   2011-01-10     10.0  WINTER  ...     134....142857   886.694316
713 2012-12-31    731.0  WINTER  ...      920.0  1531.428571   887.135250

[714 rows x 29 columns]

    def test_no_forbidden_features(feats):
        """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
        construction, so this cannot discover a *new* leaky column. What it
        catches is someone editing feature_columns() or FORBIDDEN -- which is
        exactly the fault the Step 7 hook demonstrates."""
        cols = set(feature_columns(feats))
>       assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"
E       AssertionError: forbidden columns in feature set: {'casual'}
E       assert not ({'atemp', 'casual', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_7', 'cnt_std_7', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'mnth', ...})

tests\test_leakage.py:31: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: fo...
1 failed, 16 passed in 1.65s
```

### Hook stderr

**The hook did not fire on its own.** `.claude/settings.json` has
`permissions` but no `hooks` section, so nothing runs `check_leakage.sh`
after an edit, and the Edit returned no hook output. The output below came
from running the script by hand with a sample PostToolUse payload for
`src/features.py`. Exit code 2, which is the code that would send it back to
Claude. The garbled `134....142857` in the first lines is real: pytest had
already shortened the table, and the hook keeps only the last 20 lines.

```text
Leakage tests failed after editing c:/Users/caram/projects/bikeshare-open-starter/src/features.py:
feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7    cnt_std_7
0   2011-01-10     10.0  WINTER  ...     134....142857   886.694316
713 2012-12-31    731.0  WINTER  ...      920.0  1531.428571   887.135250

[714 rows x 29 columns]

    def test_no_forbidden_features(feats):
        """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
        construction, so this cannot discover a *new* leaky column. What it
        catches is someone editing feature_columns() or FORBIDDEN -- which is
        exactly the fault the Step 7 hook demonstrates."""
        cols = set(feature_columns(feats))
>       assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"
E       AssertionError: forbidden columns in feature set: {'casual'}
E       assert not ({'atemp', 'casual', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_7', 'cnt_std_7', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'mnth', ...})

tests\test_leakage.py:31: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: fo...
1 failed, 8 passed in 0.60s
```

### Repair

**Fix:** reverted the one line in `feature_columns()`, with the Edit tool:

```diff
-    return [c for c in numeric if c not in FORBIDDEN] + ["casual"]  # EXERCISE 2: seeded leak
+    return [c for c in numeric if c not in FORBIDDEN]
```

**Verification:**
- `python -m pytest tests/ -q`: `17 passed in 1.45s`
- the hook, run by hand with the same payload: exit code 0, no stderr
- `python -m src.features`: `OK features: 714 rows, 15 features`, with
  `casual` absent

**Turns to repair: 1.** One user turn ("fix the fault"), one Edit, one
verification run, no failed attempts. The test failure named the column
(`{'casual'}`) and the line, so diagnosis took no extra steps. The fix was
not prompted by the hook, which is not registered (see above). The failing
test, run by hand, is what caught the leak.
