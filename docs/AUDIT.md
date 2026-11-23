# Peer audit (Exercise 3)

- **Repository audited:** https://github.com/Atakamoto/bikeshare-open.git
- **Local checkout:** `../bikeshare-peer`, HEAD `dd5fc63` ("Add final report, target-transformation decision, and model-summary skill")
- **Auditor:** `leakage-auditor` subagent, asked to review the entire committed pipeline (not just a diff) and to stay read-only in the peer repository.
- **Peer repository unmodified:** `git status --short` in `../bikeshare-peer` was empty after the audit.

The section below is the subagent's output, verbatim. The only change is removing the two-space indent the harness adds to every line of a subagent report. Paths starting `C:\Users\caram\AppData\Local\Temp\...` point to scratchpad scripts, which are temporary and not part of either repository.

---

I reviewed peer@dd5fc63 by reading the code and rerunning everything in memory. The pipeline's numbers are sound: I found no leakage, the split is correct, and every data-derived number in `metrics.json` reproduces except the HGB row, whose gap is explained by my scikit-learn version. The real problems are a blind spot in the test suite, the effect of same-day weather on the headline score, and some stale claims in DECISIONS.md.

**How I checked, without writing to their repo:** all scripts ran from the scratchpad and imported the peer code with bytecode writing turned off. `git status` was clean before and after. I ran no `make`, no `python -m src.*` and no pytest there. One attempt to copy the repo into the scratchpad was denied by the permission system, so I imported it read-only instead. The scripts are `C:\Users\caram\AppData\Local\Temp\claude\b9cef0d18038b8f9\370c94a9-611d-4269-a606-123579adc876\scratchpad\peer_check.py` and `C:\Users\caram\AppData\Local\Temp\claude\b9cef0d18038b8f9\370c94a9-611d-4269-a606-123579adc876\scratchpad\peer_mut.py`.

**What checked out:**
- **Leakage:** the 15 features come from `FORBIDDEN` in `src/config.py:46`, not a hand-typed list. None is `casual`, `registered`, `cnt`, `cnt_2d_bfr` or a time index, and none restates same-day `cnt`. The hand-typed leaky list in `src/leakage_demo.py:18` is a deliberate demo and is not used by the pipeline.
- **Lag and rolling features:** all are built on the reindexed calendar and shift before aggregating (`src/features.py:181`, `:201-204`). I checked `cnt_lag_7` and `cnt_roll_14` against the raw calendar on all 700 rows: 0 mismatches.
- **Warm-up:** `LAG_WARMUP = max(7, 7, 14) = 14` (`config.py:72`). Exactly 28 rows are dropped: the 14 warm-up days plus 2011-03-11 to 03-24 after the missing day.
- **Split:** train runs 2011-01-17 to 2011-12-31, valid 2012-01-01 to 06-30, test 2012-07-01 to 12-31. The scaler sits inside the Ridge pipeline and is fit on train only, and the mean baseline is also fit on train.
- **Metrics:** recomputed in memory, the counts, features and baseline and Ridge scores match `metrics.json` exactly. HGB is off by about 0.01 R², and only HGB. My scikit-learn is 1.8.0 against their pinned 1.9.1, and `requirements.txt` warns that HGB drifts across versions, so that is expected.
- **REPORT claims:** the 2011 maximum of 6,043, the H1 2012 maximum of 8,362, "348 to 334 rows" and "18 passed" are all correct.

## Findings

**F1 (High, test gap): the suite cannot detect losing the calendar-gap fix.**
- **Where:** `src/features.py:181`; the tests that should catch it are `tests/test_leakage.py:126-135`, `tests/test_contract.py:22-25` and `:28-43`.
- **Failure:** I removed the reindex in memory (the reindex function made a no-op). The 2011-03-11 lag-1 then becomes 2011-03-09's count (1891), and seven days of lag-7, roll-7 and roll-14 values are off by a day. All 14 data-dependent tests still pass; the other 4 tests never read the feature table:
  - `test_lags_are_true_calendar_lags` skips 2011-03-11 because 03-10 is not in the index.
  - `test_calendar_is_complete_before_lagging` tests the helper, not whether `build_features` calls it.
  - The row-loss test allows `<= 28`, and the broken version drops only 14.
- **Fix:**
  - Change the row-loss check to `lost == allowed_loss`.
  - Assert that no rows exist for 2011-03-11 to 03-24.
  - Add a hand-computed `cnt_lag_7` / `cnt_roll_7` check on a date just after the gap, such as 2011-03-25.

**F2 (Medium, optimistic headline): Ridge's lead over persistence depends on same-day observed weather.**
- **Where:** `src/features.py:195-196`, which keeps `temp`, `atemp`, `hum`, `windspeed` and `weather_severity`; the claims are at `REPORT.md:60` and `:66`.
- **What it does to the number:** REPORT discloses the issue but says no ablation was run. I ran one on validation only: dropping the weather columns takes Ridge from R² 0.6919 / MAE 763.2 to 0.5799 / 875.7. Ridge's lead over persistence (900.6) shrinks from 137 rides to 25. The "15% MAE cut" is mostly what observed weather contributes, not lagged demand.
- **Fix:** report a weather-free (or one-day-lagged weather) Ridge row on validation next to persistence, and restate the claim accordingly.

**F3 (Medium, documentation contradicts the record): DECISIONS.md misstates when the test set was used and has stale numbers.**
- `docs/DECISIONS.md:9` says "Test set touched once, after all feature work." But at commit `70124fd`, where `cnt_roll_14` was added, `test_beats_the_mean_baseline` scored Ridge on the test split on every `make test` (old `tests/test_contract.py:49-52`). `REPORT.md:21` admits this, so the two documents contradict each other.
- `DECISIONS.md:10` says persistence is "within 0.07 R² of ridge". In `metrics.json` the gap is 0.6268 − 0.5099 = 0.117.
- `DECISIONS.md:5` quotes "honest ridge 0.583", which appears nowhere in `metrics.json`.
- **Fix:** correct all three lines to match `metrics.json` and the commit history.

**F4 (Low, overstated comparison): "persistence beats Ridge on test MAE" is within noise.**
- **Where:** `DECISIONS.md:10` and `REPORT.md:62`.
- **Evidence:** Ridge's MAE minus persistence's on test is +30.8. A paired bootstrap (5,000 resamples) gives a 95% interval of [−79.6, +137.2], which includes zero.
- **Fix:** say "no detectable difference". REPORT already uses "matches" at line 69, and DECISIONS should too.

**F5 (Medium, weak test): `test_beats_the_mean_baseline` is not tied to either baseline.**
- **Where:** `tests/test_contract.py:46-54`.
- **Failure:** it asserts Ridge validation R² > 0.4. Persistence scores 0.4507 on validation, so a Ridge scoring 0.42, worse than "yesterday again", passes. Despite the name, it never compares against the mean baseline either.
- **Fix:** assert that Ridge validation R² beats both `baseline_persistence` and `baseline_mean`, computed in the test.

**F6 (Low, vacuous tests):**
- `test_persistence_baseline_is_reported` (`test_contract.py:57-60`) only checks that a dictionary key exists. It never checks the persistence predictions, `metrics.json`, or the mean baseline.
- `test_lag_is_not_the_target` (`test_leakage.py:138-139`) passes if even one row differs.
- `test_rolling_mean_excludes_today` (`test_leakage.py:145-149`) is wrapped in an `if` with no else, so it can pass without asserting anything. It does run today, on 2011-08-20.
- The split tests (`tests/test_split.py`) check order and overlap but not the boundary dates, so a wrong `TRAIN_END` would pass.
- **Fix:**
  - Assert that persistence predictions equal `cnt_lag_1`.
  - Assert that the leakage-test window exists.
  - Pin train to 2011 only, the valid end to 2012-06-30, and the test start to 2012-07-01.

**F7 (Low, unverifiable): the target-transformation results have no committed code.**
- **Where:** `REPORT.md` section 3 and `DECISIONS.md:11`.
- **Problem:** the residual, ratio and log1p HGB numbers (for example 0.616 / 823.5) and the in-memory checks in REPORT section 2 (HGB predictions topping out at 5,512, bias of −1,235 / −378) were "in memory" only. Nothing in the repo reproduces them, so I could not verify them.
- **Fix:** commit the experiment script, or label these numbers as unreproducible.

## Verdict

No leakage and no split violation: the reported numbers are what the code produces. The three things to fix are:
1. The test suite would not catch a regression on the 2011-03-10 gap (F1).
2. The validation case for Ridge over persistence rests largely on observed weather (F2).
3. DECISIONS.md makes test-set and score claims that `metrics.json` and the git history contradict (F3).

Files reviewed are in `C:\Users\caram\projects\bikeshare-peer\` (`src\`, `tests\`, `REPORT.md`, `docs\DECISIONS.md`, `reports\metrics.json`, `requirements.txt`).



## My own verdict

I agree with most of these findings. F2 makes a good point that Ridge's advantage might be smaller in a real forecasting setting where observed weather isn't available. F3 does show that there might be concerns about how consistent the evaluation methodology is. I think that F1, F5, and F6 do show some weaknesses in the current test setup, but don't invalidate the current results. Only two findings change a number. For F2, Ridge's validation MAE over persistence falls from 137 rides to 25. For F3, DECISIONS.md reports a 0.07 R^2 gap compared to persistence but metrics.json gives 0.117. 