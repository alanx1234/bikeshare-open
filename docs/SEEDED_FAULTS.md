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
