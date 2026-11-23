# Report

## Results

The feature is `cnt_std_7`, the sample standard deviation of `cnt` over days d-7 to d-1. *Before* is the pipeline without it (commit `688ae52`, 14 features). *After* is the current pipeline (15 features), and its rows equal `reports/metrics.json` exactly. Both use the same split (348 train / 182 validation / 184 test days), the same hyperparameters and the versions pinned in `requirements.txt`. The baselines use no features, so they don't change.

| Model | Feature set | Valid R² | Valid MAE | Test R² | Test MAE |
|---|---|---|---|---|---|
| baseline_mean | before | -0.9318 | 2002.2 | -2.1441 | 2847.7 |
| baseline_mean | after | -0.9318 | 2002.2 | -2.1441 | 2847.7 |
| baseline_persistence | before | 0.4507 | 900.6 | 0.5099 | 840.1 |
| baseline_persistence | after | 0.4507 | 900.6 | 0.5099 | 840.1 |
| ridge | before | 0.6475 | 832.9 | 0.5833 | 947.1 |
| ridge | after | 0.7224 | 700.4 | 0.6356 | 840.3 |
| hgb | before | 0.2185 | 1296.6 | -0.4975 | 1972.6 |
| hgb | after | 0.0977 | 1381.6 | -0.6959 | 2108.4 |

**Reproducing the table.** Run `make all` for *after*. For *before*, run the same command in a checkout of `688ae52`.

**Test-set use.** The keep decision used validation only, and was recorded with validation numbers in `15b4c2b`. The *after* test scores were visible during the work, because `make train` prints them. The *before* test scores were first computed on 2026-11-22, for this table.

## Headline finding

The naive evaluation, with `casual` and `registered` as features, scores test R² 1.000 and is invalid, because those two columns sum to `cnt` (`python -m src.leakage_demo`). Under the temporal split, ridership grew about 65% from 2011 to 2012, and that decides the comparison: the mean baseline is strongly negative on test (R² −2.1441). Ridge is the best model but only narrowly beats the persistence baseline (yesterday's count) on test: its test R² is 0.6356 against persistence's 0.5099, yet its test MAE is 840.3 rides against 840.1, so on typical error it does not beat persistence at all (on validation its lead is clearer: R² 0.7224 vs 0.4507, MAE 700.4 vs 900.6). Gradient boosting fails because it cannot extrapolate the growing trend: trained on 2011, it cannot predict above the 2011 maximum of 6,043 rides, and 104 of the 184 test days (56.5%) are above it. Its test R² is negative (−0.6959), worse than predicting the test period's own average. It still beats the mean baseline comfortably (MAE 2108.4 vs 2847.7), so a negative R² is not the same as losing to the baseline: hgb beats the mean baseline and loses badly to persistence (MAE 2108.4 vs 840.1). Ridge and hgb use observed same-day weather, so their scores are optimistic for a real day-ahead forecast (see Exercise 5).

Adding `cnt_std_7` raised ridge's validation R² from 0.6475 to 0.7224 (MAE 832.9 → 700.4) and lowered hgb's from 0.2185 to 0.0977 (MAE 1296.6 → 1381.6), and I kept it because the ridge gain is well above the noise on 182 validation days.

## Exercise 4: target transformation

**Transformation.** HGB is trained on the day-over-day change `cnt − cnt_lag_1`, and `cnt_lag_1` is added back to its predictions, so scores are on the count scale. Features, split and hyperparameters are unchanged. `cnt_lag_1` is yesterday's count, known before today is predicted, so nothing from day *d* is used. Reproduce with `python -m src.train --residual-experiment`.

| Validation (H1 2012) | R² | MAE |
|---|---|---|
| baseline_mean | −0.9318 | 2002.2 |
| baseline_persistence | 0.4507 | 900.6 |
| ridge | **0.7224** | **700.4** |
| hgb (target `cnt`) | 0.0977 | 1381.6 |
| hgb_residual (target `cnt − cnt_lag_1`) | 0.5642 | 885.8 |

The transformation substantially improves HGB, from R² 0.0977 → 0.5642 and MAE 1381.6 → 885.8. Once `cnt_lag_1` carries the level, the trees only predict the daily change, which is similar in both years. It still trails ridge by 0.158 R² and 185.4 rides of MAE. Its edge over persistence is small (+0.114 R², 14.8 rides) and may be noise.

**Decision.** The residual transformation is defensible, because yesterday's demand is available at prediction time. It substantially improves HGB but still underperforms ridge, so the original pipeline is retained unchanged.

**Final test look (once, at the end).** The decision above was committed on validation evidence in `2522ed0`. After that, the test set was scored once with `python -m src.train --residual-experiment --final-test`. Reruns used only to check these numbers gave identical output, and no unit test scores the test split.

| Test (H2 2012) | R² | MAE |
|---|---|---|
| baseline_mean | −2.1441 | 2847.7 |
| baseline_persistence | 0.5099 | 840.1 |
| ridge | 0.6356 | 840.3 |
| hgb (target `cnt`) | −0.6959 | 2108.4 |
| hgb_residual (target `cnt − cnt_lag_1`) | 0.4761 | 990.5 |

HGB improves on test too, from R² −0.6959 → 0.4761 and MAE 2108.4 → 990.5. But its small validation edge over persistence does not hold: R² 0.4761 vs 0.5099 and MAE 990.5 vs 840.1. The decision is unchanged.

## Exercise 5: ridge vs persistence

The decision uses **validation only**. Test scores are descriptive. Five of ridge's features are weather observed on the day being predicted: `temp`, `atemp`, `hum`, `windspeed` and `weather_severity`. A forecaster working the day before would not have them, and `temp` (363.5) and `weather_severity` (−249.0) are among ridge's four largest standardised coefficients. Ridge was therefore refit without them. Reproduce with `python -m src.train --weather-ablation` (bootstrap seed 0, 5,000 draws).

| Validation (H1 2012) | R² | MAE | MAE vs persistence (95% range) |
|---|---|---|---|
| ridge, same-day weather (default) | 0.7224 | 700.4 | −200.2 [−304.4, −101.6] |
| ridge, weather from the previous day | 0.5793 | 884.2 | −16.4 [−121.2, +84.1] |
| ridge, no weather | 0.5723 | 894.6 | −6.0 [−105.5, +91.2] |
| baseline_persistence | 0.4507 | 900.6 | — |
| baseline_mean | −0.9318 | 2002.2 | — |

The ranges come from resampling the 182 days; negative means ridge is better.
- **With same-day weather,** ridge's 200-ride lead is clear.
- **Using only information available in advance,** its MAE lead is within the noise.
- **Ridge keeps a higher R² in every variant,** so it still avoids some large misses.

**Tradeoffs.** Persistence needs only yesterday's count, has nothing to fit, and follows the 2011 to 2012 growth automatically. Ridge needs a weather forecast, a 7-day gap-free history, calendar flags, periodic retraining, pinned versions, and leakage tests to keep it honest.

**Recommendation (validation only).** I would deploy persistence over ridge for now. On validation, ridge's MAE advantage over persistence is 200.2 rides only when it is given the same day's observed weather. Without it, the advantage is just 6.0 rides (16.4 with the previous day's weather), and both 95% ranges include zero. Ridge keeps a higher validation R² without weather (0.5723–0.5793 vs. 0.4507), so it avoids some large misses. But given that persistence requires only yesterday's demand and no retraining, I don't think ridge's additional complexity is currently justified. However, I would reconsider deploying ridge if reliable weather forecasts were available and further evaluation demonstrated a meaningful improvement.

**Descriptive test results (not used for the decision).**
- **Scores:** ridge has test R² 0.6356 and MAE 840.3; persistence has 0.5099 and 840.1.
- **MAE gap:** ridge's MAE minus persistence's is +0.2 rides, 95% range [−118.8, +115.6]. Ridge is closer on 80 of 184 days.
- **Shocks:** neither model handles them. On Hurricane Sandy (2012-10-29, 22 rides), ridge predicted 4,306 and persistence 4,459.

**Limitation: observed same-day weather.** The five weather features are not leakage: they are not built from `cnt`, and the leakage tests pass. They are measurements of the day being predicted, though, so every ridge and hgb score here, and in `reports/metrics.json`, is a nowcast that assumes the day's weather is known. A real deployment would use forecast weather, whose accuracy falls between the rows above; this dataset has no forecasts to measure it. The default feature set is unchanged, so scores stay comparable. The baselines use no weather.

## Attribution

**Model:** Claude Opus 5.5 (`claude-opus-5-5`, hosted by Anthropic) through Claude Code, for every session from 2026-11-19 to 2026-11-22. I did not switch models, and the starter's local Ollama model (`bikeshare-coder`) was not used. The `/leakage-auditor` subagent (`model: inherit`) and the `agent/audit.py` run that produced `reports/audit.jsonl` also used Claude Opus 5.5.

The agent is accountable for the code; I am accountable for every claim in this report.

### Generated by the agent

- **`src/features.py`:**
  - `cnt_std_7` (a1836b4)
  - `previous_day_weather()` (d85c36f)
- **`src/config.py`:**
  - `RAW_FEATURE_COLS` and `REDUNDANT_CALENDAR_COLS` (688ae52)
  - `SAME_DAY_WEATHER_FEATURES` and the bootstrap seed (d85c36f)
  - `RAW_SHA256` (7602063)
- **`src/ingest.py`:** `verify_raw()` (7602063).
- **`src/train.py`:**
  - `residual_experiment()` (2522ed0)
  - `weather_ablation()` and `paired_mae_gap()` (d85c36f)
  - `--final-test` and `include_test` (7a86749)
- **`tests/test_leakage.py`:**
  - `test_rolling_std_excludes_today`, written before the feature (714a750)
  - the six-date `test_rolling_mean_excludes_today` (72f6b03)
  - the previous-day weather tests (d85c36f)
  - the leakage tests that work under any column name (7a86749)
- **`tests/test_contract.py`:**
  - `test_every_raw_column_is_classified` (688ae52)
  - `test_unknown_weather_label_raises` (087d93a)
  - the validation rewrite of `test_beats_the_mean_baseline` (d85c36f)
  - `test_raw_data_is_unchanged` (7602063)
- **`tests/test_split.py`:** the experiment tests (2522ed0, d85c36f).
- **Hooks:** `.claude/hooks/check_leakage.sh` and the hook registration in `.claude/settings.json` (fb1f629, 72f6b03).
- **Skill:** `.claude/skills/validation-summary/SKILL.md` (fd8218b).
- **Seeded faults:**
  - the three fault edits and their repairs, with the text of `docs/SEEDED_FAULTS.md` (714a750 to f402ae2)
  - the fault 4 run in a scratch clone (7602063)
- **`docs/AUDIT.md`:** the subagent output is verbatim; the framing is agent-written.
- **Prose:** drafts of this report and README.md, and the wording of the DECISIONS.md lines. The Exercise 4 and 5 decisions and the `cnt_std_7` rationale are in my words, and I edited the rationale by hand in d885671.

### Decisions that were mine

Each one traces to a line in `docs/DECISIONS.md`.

- **What counts as leakage.**
  - Keep the starter's exclusions: `casual` and `registered`, `cnt_2d_bfr`, and the time indexes.
  - Classify every raw column, with `season`, `mnth` and `weekday` as redundant calendar columns, not leakage.
  - No model input may move when same-day `cnt`, `casual` or `registered` changes.

  *DECISIONS: the three starter "Exclude" lines, 2026-11-21 (688ae52), and "Add behavioural leakage tests".*
- **How to split.** By date: 2011 / H1 2012 / H2 2012. *DECISIONS: "Split 2011 / H1 2012 / H2 2012" and its correction.*
- **Which baselines.** Mean and persistence next to every score, with a unit test that requires ridge to beat both on validation. *DECISIONS: "Report mean and persistence baselines" and "`test_beats_the_mean_baseline` now scores validation".*
- **Whether to keep my feature.** Keep `cnt_std_7`. *DECISIONS: "Keep `cnt_std_7`" and "Kept: …".*
- **Whether the Exercise 4 transformation is defensible.** It is, but the pipeline stays untransformed, and test was scored once, after the decision. *DECISIONS: "Residual target for HGB" and "Exercise 4 final test look".*
- **Whether the answer is believable.**
  - Results come only from the pinned environment.
  - Weather-based scores are reported as nowcasts.
  - The deployment choice of persistence rests on validation only.

  *DECISIONS: "Metrics come from the pinned `.venv`", "Keep the five same-day weather observations", and "The Exercise 5 deployment decision".*
- **Enforcement.**
  - Run the hook on the full suite.
  - Add `/validation-summary` to CLAUDE.md.
  - Track `reports/`.
  - Catch fault 4 with a raw-data hash check.

  *DECISIONS: 2026-11-21 (fb1f629, 72f6b03, 087d93a), 2026-11-22 (fd8218b), "Track `reports/metrics.json`", and "Fault 4".*

### Reproducibility and corrections

1. **HGB numbers.** Early HGB numbers came from the system Python (scikit-learn 1.8.0) instead of the pinned `.venv` (1.9.1). HGB drifts across releases; ridge and the baselines matched exactly. Under the pins, the earlier validation figures changed as follows, with no conclusion changed:

   | Validation, R² / MAE | Earlier (1.8.0) | Pinned (1.9.1) |
   |---|---|---|
   | hgb | 0.0964 / 1382.9 | 0.0977 / 1381.6 |
   | hgb_residual | 0.5714 / 870.6 | 0.5642 / 885.8 |
   | hgb before `cnt_std_7` | 0.2368 / 1291 | 0.2185 / 1296.6 |
2. **The Exercise 5 ablation.** It first ran from an uncommitted script with no seed. It is now `--weather-ablation`, with a fixed seed.
3. **Test-set access.**
   - **A gated unit test:** from the starter's first commit until 2026-11-22, `test_beats_the_mean_baseline` asserted ridge **test** R² > 0.4 on every `pytest` run, including every hook run. It never failed, and nothing was tuned on it. It now compares ridge with both baselines on validation.
   - **The first Exercise 5 draft:** it cited test R² and MAE. That draft was never committed, and the decision now rests on validation.
4. **`reports/audit.jsonl` (`agent/audit.py`, Claude Opus 5.5).**
   - **Earlier runs flagged:**
     - test numbers in the Exercise 5 decision
     - no mean baseline in the weather ablation
     - an out-of-date README
     - uncommitted work
     - `make all` silently using an unpinned interpreter on PATH
     - same-day weather

     All of these are fixed above except same-day weather, which is acknowledged as a limitation in Exercise 5. `make train` now exits 1 unless the installed versions match `requirements.txt` (dbd24b7).
   - **The final run on the finished repository** reports no leakage, a valid temporal split, both baselines and a reproducible pipeline, with no findings.
