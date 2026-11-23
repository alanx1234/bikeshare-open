# Report

## Exercise 4: residual target for HGB

**Question.** HGB trained on 2011 cannot predict counts above the 2011 range, and 2012 ridership is about 65% higher. Does training HGB on the day-over-day change, `cnt - cnt_lag_1`, fix that?

**Method.**
- HGB is trained on `cnt - cnt_lag_1`, then `cnt_lag_1` is added back to its predictions, so every score is on the original count scale.
- Features (15), the temporal split (train 2011, validation H1 2012) and hyperparameters (`random_state=0, max_iter=300`) are the same as the default pipeline. Every model is a `clone()` of `src.train.MODELS`.
- Validation only. The test set was not scored and `reports/metrics.json` was not written; its SHA-256 was identical before and after the run.
- Reproduce with `python -m src.train --residual-experiment`. `tests/test_split.py` checks that removing the test-period rows changes none of the numbers, and that the persistence MAE matches a hand calculation.

**Availability.** `cnt_lag_1` is yesterday's count, known before today is predicted, so neither the target transformation nor the reconstruction uses anything from day *d*.

**Validation results (H1 2012, 182 days, count scale):**

| Model | R² | MAE |
|---|---|---|
| baseline_mean | −0.9318 | 2002.2 |
| baseline_persistence | 0.4507 | 900.6 |
| ridge | **0.7224** | **700.4** |
| hgb (target `cnt`) | 0.0964 | 1382.9 |
| hgb_residual (target `cnt − cnt_lag_1`) | 0.5714 | 870.6 |

**Findings.**
- The transformation substantially improves HGB: R² 0.0964 → 0.5714, MAE 1382.9 → 870.6. This supports the extrapolation explanation. Once `cnt_lag_1` carries the level, the trees only have to predict the day-to-day change, which is similar in 2011 and 2012.
- It still underperforms ridge by 0.151 R² and 170.2 rides of MAE.
- Its edge over persistence is small: +0.121 R² and 30.0 rides of MAE. No bootstrap was run, so the MAE gap may be within the noise on 182 days.

**Decision.** The residual transformation is defensible, because yesterday's demand is available at prediction time. It substantially improves HGB but still underperforms ridge, so the original pipeline is retained unchanged. The experiment stays in `src/train.py` as an optional flag, so these results remain reproducible. See `docs/DECISIONS.md`.
