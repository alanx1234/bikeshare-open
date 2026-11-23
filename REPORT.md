# Report

## Results

The feature is `cnt_std_7`, the sample standard deviation of `cnt` over days d-7 to d-1. Rows marked *before* are the pipeline without it (commit `688ae52`, 14 features). Rows marked *after* are the current pipeline (15 features). The *after* rows equal `reports/metrics.json` exactly. Both versions use the same split (348 train / 182 validation / 184 test days) and the same hyperparameters, under the versions pinned in `requirements.txt`. The two baselines don't use any features, so they are identical before and after.

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

**Reproduce.**
- *After:* run `python -m src.features` then `python -m src.train` in the `.venv`.
- *Before:* run the same two commands in a checkout of `688ae52` (`git worktree add <dir> 688ae52`).
- Rerunning commit `a1836b4`, which added the feature, gives a `metrics.json` identical to the current one.

**How the test set was used.**
- **For the decision:** the keep decision for `cnt_std_7` was made on validation only, and recorded with validation numbers in commit `15b4c2b` (`docs/DECISIONS.md`).
- **Seen during iteration:** the default `python -m src.train` also printed the *after* test scores during the work. A test-gated unit test existed until 2026-11-22 (see *Reproducibility and corrections* under Attribution, item 3).
- **Computed late:** the *before* test scores were first computed under the pinned versions on 2026-11-22, after the decision, for this table.

## Headline finding

The naive evaluation, with `casual` and `registered` as features, scores test R² 1.000 and is invalid, because those two columns sum to `cnt` (`python -m src.leakage_demo`). Under the temporal split, ridership grew about 65% from 2011 to 2012, and that decides the comparison: the mean baseline is strongly negative on test (R² −2.1441). Ridge is the best model but only narrowly beats the persistence baseline (yesterday's count) on test: its test R² is 0.6356 against persistence's 0.5099, yet its test MAE is 840.3 rides against 840.1, so on typical error it does not beat persistence at all (on validation its lead is clearer: R² 0.7224 vs 0.4507, MAE 700.4 vs 900.6). Gradient boosting fails because it cannot extrapolate the growing trend: trained on 2011, it cannot predict above the 2011 maximum of 6,043 rides, and 104 of the 184 test days (56.5%) are above it. Its test R² is negative (−0.6959), worse than predicting the test period's own average. It still beats the mean baseline comfortably (MAE 2108.4 vs 2847.7), so a negative R² is not the same as losing to the baseline: hgb beats the mean baseline and loses badly to persistence (MAE 2108.4 vs 840.1). Ridge and hgb use observed same-day weather, so their scores are optimistic for a real day-ahead forecast (see Exercise 5, *Limitations*).

Adding `cnt_std_7` raised ridge's validation R² from 0.6475 to 0.7224 (MAE 832.9 → 700.4) and lowered hgb's from 0.2185 to 0.0977 (MAE 1296.6 → 1381.6), and I kept it because the ridge gain is well above the noise on 182 validation days.

## Exercise 4: target transformation

**Question.** HGB trained on 2011 cannot predict counts above the 2011 range, and 2012 ridership is about 65% higher. Does training HGB on the day-over-day change, `cnt - cnt_lag_1`, fix that?

**Method.**
- HGB is trained on `cnt - cnt_lag_1`, then `cnt_lag_1` is added back to its predictions, so every score is on the original count scale.
- Features (15), the temporal split (train 2011, validation H1 2012) and hyperparameters (`random_state=0, max_iter=300`) are the same as the default pipeline. Every model is a `clone()` of `src.train.MODELS`.
- Numbers are from the pinned environment in `requirements.txt` (scikit-learn 1.9.1, pandas 3.0.5); see *Reproducibility and corrections* under Attribution for why the first version of this table differed.
- Decided on validation only. The test set was scored once, at the end, after the decision was committed (see *Final test look*). `reports/metrics.json` was never written by the experiment; its SHA-256 was identical before and after each run.
- Reproduce with `python -m src.train --residual-experiment`. `tests/test_split.py` checks that removing the test-period rows changes none of the numbers, and that the persistence MAE matches a hand calculation.

**Availability.** `cnt_lag_1` is yesterday's count, known before today is predicted, so neither the target transformation nor the reconstruction uses anything from day *d*.

**Validation results (H1 2012, 182 days, count scale):**

| Model | R² | MAE |
|---|---|---|
| baseline_mean | −0.9318 | 2002.2 |
| baseline_persistence | 0.4507 | 900.6 |
| ridge | **0.7224** | **700.4** |
| hgb (target `cnt`) | 0.0977 | 1381.6 |
| hgb_residual (target `cnt − cnt_lag_1`) | 0.5642 | 885.8 |

**Findings.**
- The transformation substantially improves HGB: R² 0.0977 → 0.5642, MAE 1381.6 → 885.8. This supports the extrapolation explanation. Once `cnt_lag_1` carries the level, the trees only have to predict the day-to-day change, which is similar in 2011 and 2012.
- It still underperforms ridge by 0.158 R² and 185.4 rides of MAE.
- Its edge over persistence is small: +0.114 R² and 14.8 rides of MAE. No bootstrap was run, so the MAE gap may be within the noise on 182 days.

**Decision.** The residual transformation is defensible, because yesterday's demand is available at prediction time. It substantially improves HGB but still underperforms ridge, so the original pipeline is retained unchanged. The experiment stays in `src/train.py` as an optional flag, so these results remain reproducible. See `docs/DECISIONS.md`.

**Final test look (once, at the end).** The decision above was committed on validation evidence in `2522ed0`. After that, on 2026-11-22, the test set was scored once with `python -m src.train --residual-experiment --final-test`. Nothing was changed after that look. Later runs of the same command, used only to check that the numbers below are reproduced exactly, gave identical output. None of the unit tests scores the test split.

| Test (H2 2012, 184 days, count scale) | R² | MAE |
|---|---|---|
| baseline_mean | −2.1441 | 2847.7 |
| baseline_persistence | 0.5099 | 840.1 |
| ridge | 0.6356 | 840.3 |
| hgb (target `cnt`) | −0.6959 | 2108.4 |
| hgb_residual (target `cnt − cnt_lag_1`) | 0.4761 | 990.5 |

- **HGB improves substantially on test too:** R² −0.6959 → 0.4761, MAE 2108.4 → 990.5.
- **Its small validation edge over persistence does not hold:** on test it loses, R² 0.4761 vs 0.5099 and MAE 990.5 vs 840.1. That is consistent with the validation note that the 14.8-ride gap might be noise.
- **The decision is unchanged:** the transformation is defensible, ridge stays ahead, and the committed pipeline is untransformed. The four default-model rows equal `reports/metrics.json`.


## Exercise 5: ridge vs persistence

**Question.** Should the deployed forecaster be ridge or the persistence baseline (predict yesterday's count)?

**Basis for the decision.** The decision uses **validation only** (H1 2012, 182 days). Test scores (H2 2012) appear at the end of this section as descriptive results. They were not used to choose between the models. Every number in this section reproduces with `python -m src.train --weather-ablation`. The bootstrap seed (0) and draw count (5,000) are set in `src/config.py`.

**Evidence: validation, with both baselines.** Five of ridge's features are weather observed on the day being predicted: `temp`, `atemp`, `hum`, `windspeed` and `weather_severity`. A forecast made in advance cannot know them. `temp` (363.5) and `weather_severity` (−249.0) are among ridge's four largest standardised coefficients. So ridge is shown as configured by default, and refit without that information:

| Validation (H1 2012, 182 days) | R² | MAE | MAE vs persistence (95% range) |
|---|---|---|---|
| ridge, same-day weather (default) | 0.7224 | 700.4 | −200.2 [−304.4, −101.6] |
| ridge, weather from the previous day | 0.5793 | 884.2 | −16.4 [−121.2, +84.1] |
| ridge, no weather | 0.5723 | 894.6 | −6.0 [−105.5, +91.2] |
| baseline_persistence | 0.4507 | 900.6 | — |
| baseline_mean | −0.9318 | 2002.2 | — |

The 95% ranges come from resampling the 182 days 5,000 times. Each gives ridge's MAE minus persistence's, so a negative value means ridge is better.
- **With same-day weather, ridge is clearly better.** Its lead is 200 rides, and the range excludes zero. But that is a nowcast: it assumes the day's weather is known (see *Limitations*).
- **Using only information available in advance, the MAE advantage is within the noise.** That means no weather, or the previous day's weather: 6.0 or 16.4 rides, and both ranges include zero.
- **Ridge keeps a higher R² in every variant.** Even without weather it is 0.12–0.13 above persistence, so it still avoids some large misses.
- **Every variant beats the mean baseline by a wide margin.** That is expected, because ridership grew about 65% from 2011 to 2012.

A deployed model would use forecast weather. Its accuracy falls somewhere between these rows, and this dataset has no forecasts to measure where.

**Tradeoffs.**
- **Predictive performance (validation):**
  - Ridge leads on R² in every variant.
  - It leads on MAE only when it is given same-day observed weather. Using only information available in advance, its MAE matches persistence within the noise.
- **Input availability:**
  - Persistence needs only yesterday's count.
  - Ridge needs today's weather, which in practice means a forecast; at least 7 days of gap-free history; and calendar flags.
- **Maintenance:**
  - Persistence has nothing to fit and follows the 2011 to 2012 growth automatically.
  - Ridge's coefficients are learned on 2011 levels, so it needs periodic retraining, pinned library versions, and leakage tests to keep the lag features honest.
- **Deployment complexity:**
  - Persistence is one lookup.
  - Ridge needs a feature pipeline, a weather-forecast dependency, a stored model with versioning, and a policy for days with missing data.

**Recommendation (validation only).** I would deploy persistence over ridge for now. On validation, ridge's MAE advantage over persistence is 200.2 rides only when it is given the same day's observed weather. Without it, the advantage is just 6.0 rides (16.4 with the previous day's weather), and both 95% ranges include zero. Ridge keeps a higher validation R² without weather (0.5723–0.5793 vs. 0.4507), so it avoids some large misses. But given that persistence requires only yesterday's demand and no retraining, I don't think ridge's additional complexity is currently justified. However, I would reconsider deploying ridge if reliable weather forecasts were available and further evaluation demonstrated a meaningful improvement.

**Descriptive test results (H2 2012, 184 days; not used for the decision).** These are the default models from `reports/metrics.json`, with the default 15 features including same-day weather:

| Test (H2 2012) | R² | MAE |
|---|---|---|
| ridge (15 features) | 0.6356 | 840.3 |
| baseline_persistence | 0.5099 | 840.1 |
| baseline_mean | −2.1441 | 2847.7 |

- **MAE gap:** ridge's MAE minus persistence's is +0.2, 95% range [−118.8, +115.6]. Ridge is closer than persistence on 80 of 184 days.
- **Shocks:** neither model handles them. On Hurricane Sandy (2012-10-29, 22 rides), ridge predicted 4,306 and persistence 4,459.
- **Consistency with validation:** these results agree with the validation conclusion, but the decision does not rest on them.


### Limitations: observed same-day weather

The default feature set includes five same-day weather observations: `temp`, `atemp`, `hum`, `windspeed` and `weather_severity` (listed in `src/config.py` as `SAME_DAY_WEATHER_FEATURES`). They are **not leakage**: they are not built from `cnt`, and the leakage tests pass. They are measurements of the day being predicted, though, so a forecaster working the evening before would not have them. That has three consequences:

- **Ridge and HGB scores are nowcast scores.** Every ridge and HGB score in this report and in `reports/metrics.json` assumes that day's weather is known exactly. They overstate what a day-ahead forecaster would achieve.
- **The size of the overstatement is measured.** On validation, without same-day weather, ridge's MAE lead over persistence falls from 200.2 rides to 6.0, or 16.4 with weather from the previous day; both 95% ranges include zero (Exercise 5). Ridge's R² falls from 0.7224 to 0.5723–0.5793.
- **A real deployment would use forecast weather.** Its accuracy lies somewhere between these rows. This dataset has no weather forecasts, so that can't be measured here.

The default feature set is deliberately **unchanged**: the scores stay comparable with every earlier result. The scores should be read as "if today's weather were known", and any deployment claim has to be checked against the weather-free rows. The persistence and mean baselines use no weather and are unaffected.

## Attribution

**Model:** Claude Opus 5.5 (`claude-opus-5-5`, hosted by Anthropic) through Claude Code, for every session from 2026-11-19 to 2026-11-22. I did not switch models, and the starter's local Ollama model (`bikeshare-coder`) was not used. The `/leakage-auditor` subagent (`model: inherit`) and the `agent/audit.py` run that produced `reports/audit.jsonl` also used Claude Opus 5.5.

The agent is accountable for the code; I am accountable for every claim in this report. I reviewed and committed each change. Every number above can be regenerated from the commands named next to it.

### Generated by the agent

- **`src/features.py`:**
  - the `cnt_std_7` line (a1836b4)
  - `previous_day_weather()`, used by the weather ablation only (d85c36f)
- **`src/config.py`:**
  - `RAW_FEATURE_COLS` and `REDUNDANT_CALENDAR_COLS` with their comments (688ae52)
  - `SAME_DAY_WEATHER_FEATURES`, `BOOTSTRAP_SEED` and `BOOTSTRAP_DRAWS` (d85c36f)
- **`src/train.py`:**
  - `residual_experiment()` and `--residual-experiment` (2522ed0)
  - `--final-test`, the single Exercise 4 test look, and `include_test=False` in `weather_ablation()`, so unit tests never score test (7a86749)
  - `weather_ablation()`, `paired_mae_gap()` and `--weather-ablation` (d85c36f)
- **`tests/test_leakage.py`:**
  - `test_rolling_std_excludes_today`, written before the feature (714a750)
  - the six-date `test_rolling_mean_excludes_today` and `_raw_counts_by_date()` (72f6b03)
  - the two previous-day weather tests (d85c36f)
  - `test_no_feature_sees_same_day_or_future_cnt` and `test_no_feature_depends_on_target_components`, which catch a leak under any column name (7a86749)
- **`tests/test_contract.py`:**
  - `test_every_raw_column_is_classified` (688ae52)
  - `test_unknown_weather_label_raises` (087d93a)
  - the validation-based rewrite of `test_beats_the_mean_baseline` (d85c36f)
- **`tests/test_split.py`:** the residual-experiment, bootstrap and ablation-baseline tests (2522ed0, d85c36f).
- **Hooks and permissions:**
  - the Windows path fix and full-suite run in `.claude/hooks/check_leakage.sh`
  - the hook registration in `.claude/settings.json`
  - `.gitattributes`

  (fb1f629, 72f6b03)
- **`.claude/skills/validation-summary/SKILL.md`** and its CLAUDE.md entry (fd8218b).
- **Seeded faults:** the three fault edits and their repairs, and the text of `docs/SEEDED_FAULTS.md`, with captured test output and hook stderr (714a750 to f402ae2).
- **`docs/AUDIT.md`:** the auditor's report is the `/leakage-auditor` subagent's output, verbatim. The framing around it was also agent-written.
- **Prose:**
  - the drafts of every section of this report
  - the Windows section of README.md
  - the wording of the `docs/DECISIONS.md` lines that record my decisions

  The Exercise 4 and 5 decisions and the `cnt_std_7` keep rationale are in my own words. I edited the rationale by hand in d885671.

### Decisions that were mine

Each one traces to a line in `docs/DECISIONS.md`.

- **What counts as leakage.** I kept the starter's exclusions: `casual` and `registered` (they sum to `cnt`), the unverified `cnt_2d_bfr`, and the time indexes. I required every raw column to be classified, and classed `season`, `mnth` and `weekday` as redundant calendar columns, not leakage. I also required that no model input change when same-day `cnt`, `casual` or `registered` changes, whatever the column is called. *DECISIONS: "Exclude `casual`, `registered`", "Exclude `cnt_2d_bfr`", "Exclude `instant`…", 2026-11-21 (688ae52), and "Add behavioural leakage tests".*
- **How to split.** By date: train 2011, validation H1 2012, test H2 2012. Test-set use is disclosed in *Reproducibility and corrections* below. *DECISIONS: "Split 2011 / H1 2012 / H2 2012" and its correction.*
- **Which baselines.** Mean and persistence next to every score, and a unit test that requires ridge to beat both on validation, not a threshold on test. *DECISIONS: "Report mean and persistence baselines", and 2026-11-22 "`test_beats_the_mean_baseline` now scores validation".*
- **Whether to keep my feature.** Keep `cnt_std_7`: validation R² rose from 0.6475 to 0.7224 for ridge and fell from 0.2185 to 0.0977 for hgb. *DECISIONS: "Keep `cnt_std_7`" and "Kept: …".*
- **Whether the Exercise 4 transformation is defensible.** It is, because yesterday's count is available at prediction time. It still loses to ridge, so the pipeline is unchanged. Test was scored once, after the decision was committed. *DECISIONS: 2026-11-22 "Residual target for HGB" and "Exercise 4 final test look".*
- **Whether the answer is believable.**
  - Results come only from the pinned environment.
  - Same-day weather stays in the features, but the scores are reported as nowcasts.
  - The deployment choice of persistence over ridge rests on validation only.

  *DECISIONS: 2026-11-22 "Metrics come from the pinned `.venv`", "Keep the five same-day weather observations", "The Exercise 5 deployment decision".*
- **Enforcement and agent configuration.** Run the hook on the full suite after it missed fault 3, add `/validation-summary` to CLAUDE.md, and track `reports/`. *DECISIONS: 2026-11-21 (fb1f629, 72f6b03, 087d93a), 2026-11-22 (fd8218b), and "Track `reports/metrics.json`".*

### Reproducibility and corrections (2026-11-22)

A self-audit (`reports/audit.jsonl`) found that some numbers in this report could not be reproduced. The corrections:

**1. HGB numbers came from the wrong environment.** The first versions of the Exercise 4 table, and of `docs/DECISIONS.md`, were produced with the system Python, not the project `.venv`:

| | Used before | Pinned in `requirements.txt` |
|---|---|---|
| scikit-learn | 1.8.0 | 1.9.1 |
| pandas | 2.3.3 | 3.0.5 |
| numpy | 2.3.5 | 2.5.3 |
| pyarrow | 22.0.0 | 26.0.1 |

HistGradientBoostingRegressor's results change between scikit-learn releases even with `random_state=0`, and `requirements.txt` warns about exactly this. Ridge and both baselines matched to every printed digit in both environments; only the HGB rows moved. `python -m src.features` and `python -m src.train` were rerun in the `.venv`: the regenerated `reports/metrics.json` was byte-identical to the audit's rerun, and the raw data's SHA-256 was unchanged (`a6bed157…5ad9dc`).

| Validation | Before (sklearn 1.8.0) | Pinned (sklearn 1.9.1) |
|---|---|---|
| hgb R² / MAE | 0.0964 / 1382.9 | 0.0977 / 1381.6 |
| hgb_residual R² / MAE | 0.5714 / 870.6 | 0.5642 / 885.8 |
| hgb without `cnt_std_7`, R² / MAE | 0.2368 / 1291 | 0.2185 / 1296.6 |

On test, hgb also moved, from −0.7231 / 2135.7 to −0.6959 / 2108.4. The conclusions don't change: the residual target still substantially improves HGB and still trails ridge, and `cnt_std_7` still helps ridge and hurts HGB. Its edge over persistence on MAE is smaller than first reported (14.8 rides, not 30.0).

**2. Exercise 5 was not reproducible.** Its ablation and bootstrap came from a script outside the repository, with no recorded seed. They now run with `python -m src.train --weather-ablation`, which uses a fixed seed and gives identical output on every run. Three 95% ranges changed by up to 4.6 rides, because each comparison now gets its own seeded generator. The point estimates and every conclusion are unchanged.

**3. Test-set access.** Three ways the test set was used during development:

- **A test gated on test performance.** `test_beats_the_mean_baseline` in `tests/test_contract.py` had been in the repository since the starter's initial commit (2026-11-19). It fit ridge and asserted **test-set** R² > 0.4 on every `pytest` run. That means every `make test`, and from 2026-11-21 every PostToolUse hook run after each `src/` edit, because the hook was widened to the full suite then. It never compared against a baseline, despite its name.
  - It never failed, so it never printed a test score, and no feature or hyperparameter was chosen because of it.
  - Still, a pass/fail gate on test performance broke the "never tune on test" rule, and every change in Exercises 1–5 was made with it in place.
  - It now scores **validation** and asserts that ridge beats `baseline_mean` and `baseline_persistence`, both fit in the test.
- **The default pipeline reports test scores.** `python -m src.train` prints and saves test scores for every model, and those were visible during the work.
- **Exercise 5 first used test numbers in a decision.** The first version of the deployment recommendation cited test R² (0.6356 vs. 0.5099) and test MAE (840.3 vs. 840.1). That made the test set part of model selection. On 2026-11-22 the recommendation was rewritten to rest on validation only, where the weather-free ablation supports the same choice on its own. The test scores, test bootstrap, days-closer count and Sandy predictions remain only as descriptive results. The original version was never committed. Its first two sentences read: *"I would deploy persistence over ridge for now. Although ridge achieves a higher test R² (0.6356 vs. 0.5099), their test MAEs are nearly identical (840.3 vs. 840.1)."*

**4. `reports/audit.jsonl`.** The latest `python agent/audit.py . --out reports/audit.jsonl` run (Claude Opus 5.5) found no leakage, a valid temporal split and both baselines reported. It flagged five issues; each is addressed in this report:
- **The Exercise 5 decision used test numbers.** Fixed: the decision now rests on validation only, and test scores are descriptive.
- **Same-day weather.** Acknowledged, not changed: see Exercise 5, *Limitations*.
- **The weather ablation lacked a mean baseline.** Fixed.
- **`make` is not available on Windows, and the README test count was stale.** Fixed with the README's Windows section. The grader's `make all` path is unchanged.
- **The work was uncommitted.** Fixed by committing it.

The JSON line itself reflects the repository before those fixes.
