---
name: validation-summary
description: Summarise one model's validation R² and MAE against the mean and persistence baselines, read-only. Use when someone asks how a model did on validation or whether it beats the baselines.
argument-hint: <model> (baseline_mean | baseline_persistence | ridge | hgb | hgb_residual)
allowed-tools: Read, Bash(python -m src.train --residual-experiment)
---

# Validation summary: $ARGUMENTS

Report how `$ARGUMENTS` did on the **validation set** (H1 2012, 182 days)
and whether it improves on both baselines.

## Hard rules

- **Read-only.** Do not create, edit or delete any file. Do not run
  `make`, plain `python -m src.train` (it overwrites
  `reports/metrics.json`) or `python -m src.features` (it overwrites the
  parquet file).
- **Validation only.** Do not score, read out or quote test-set numbers.
  `reports/metrics.json` contains test scores, so do not use it as the
  source. If the user asks for test numbers, say this skill does not
  report them.

## Steps

1. **Get the numbers.** Run exactly:

   `python -m src.train --residual-experiment`

   It fits on 2011, scores validation only and writes nothing. Its JSON
   has `n_train`, `n_valid` and an `{r2, mae}` entry for each of
   `baseline_mean`, `baseline_persistence`, `ridge`, `hgb` and
   `hgb_residual`, all on the original count scale.
   - If it fails because `data/processed/features.parquet` is missing,
     stop. Tell the user to run `make features` (or
     `python -m src.features`) themselves; do not run it.

2. **Check the argument.** If `$ARGUMENTS` is empty or is not one of the
   five keys above, list the valid keys and stop. Do not guess.

3. **Report** a table with the model and both baselines, then the
   differences:

   | Model | Valid R² | Valid MAE |
   |---|---|---|
   | `$ARGUMENTS` | … | … |
   | baseline_persistence | … | … |
   | baseline_mean | … | … |

   - ΔR² and ΔMAE against each baseline. For MAE, negative means fewer
     rides of error.
   - If `$ARGUMENTS` is itself a baseline, compare it with the other
     baseline only.

4. **Verdict.** Say plainly whether it improves on each baseline:
   - **Persistence is the bar that matters.** The mean baseline is
     easy to beat, because ridership grew about 65% from 2011 to 2012.
   - **Treat an MAE gap under about 100 rides as no detectable
     difference.** On these 182 days, a resampled 95% range for a
     model-vs-persistence MAE gap is about ±100 rides wide (REPORT.md,
     Exercise 5). Don't call a smaller gap an improvement.
   - **Report a negative R² as a finding**, not an error.
   - **Same-day weather.** If the model uses any of `temp`, `atemp`,
     `hum`, `windspeed` or `weather_severity` (every model except the
     baselines does), add that these are same-day observations, so the
     score is optimistic for a real forecast. On validation, removing
     them cut ridge's MAE lead over persistence from about 200 rides
     to about 6.

Keep the reply short: the table, the differences, and a verdict of two
or three sentences.
