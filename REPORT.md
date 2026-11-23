# Report

## Exercise 4: residual target for HGB

**Question.** HGB trained on 2011 cannot predict counts above the 2011 range, and 2012 ridership is about 65% higher. Does training HGB on the day-over-day change, `cnt - cnt_lag_1`, fix that?

**Method.**
- HGB is trained on `cnt - cnt_lag_1`, then `cnt_lag_1` is added back to its predictions, so every score is on the original count scale.
- Features (15), the temporal split (train 2011, validation H1 2012) and hyperparameters (`random_state=0, max_iter=300`) are the same as the default pipeline. Every model is a `clone()` of `src.train.MODELS`.
- Numbers are from the pinned environment in `requirements.txt` (scikit-learn 1.9.1, pandas 3.0.5); see *Reproducibility and corrections* below for why the first version of this table differed.
- Validation only. The test set was not scored and `reports/metrics.json` was not written; its SHA-256 was identical before and after the run.
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


## Exercise 5: ridge vs persistence for deployment

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


## Limitations: observed same-day weather

The default feature set includes five same-day weather observations: `temp`, `atemp`, `hum`, `windspeed` and `weather_severity` (listed in `src/config.py` as `SAME_DAY_WEATHER_FEATURES`). They are **not leakage**: they are not built from `cnt`, and the leakage tests pass. They are measurements of the day being predicted, though, so a forecaster working the evening before would not have them. That has three consequences:

- **Ridge and HGB scores are nowcast scores.** Every ridge and HGB score in this report and in `reports/metrics.json` assumes that day's weather is known exactly. They overstate what a day-ahead forecaster would achieve.
- **The size of the overstatement is measured.** On validation, without same-day weather, ridge's MAE lead over persistence falls from 200.2 rides to 6.0, or 16.4 with weather from the previous day; both 95% ranges include zero (Exercise 5). Ridge's R² falls from 0.7224 to 0.5723–0.5793.
- **A real deployment would use forecast weather.** Its accuracy lies somewhere between these rows. This dataset has no weather forecasts, so that can't be measured here.

The default feature set is deliberately **unchanged**: the scores stay comparable with every earlier result. The scores should be read as "if today's weather were known", and any deployment claim has to be checked against the weather-free rows. The persistence and mean baselines use no weather and are unaffected.

## Reproducibility and corrections (2026-11-22)

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
