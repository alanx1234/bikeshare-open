# Decisions

One line per methodological decision: what you chose, why, and what it changed.
Agents append here via the `/new-feature` skill; you append here by hand.

- Exclude `casual`, `registered`: they sum to `cnt` exactly. Leaky model R^2 1.000 -> honest ridge 0.583.
- Exclude `cnt_2d_bfr`: a shipped 2-day lag we cannot test the alignment of. Build our own lags instead.
- Exclude `instant`, `yr`, `days_since_2011`: time indexes let a tree predict a flat constant past 2011 and a linear model extrapolate a trend we have no grounds for.
- Split 2011 / H1 2012 / H2 2012 by date. Test set touched once, after all feature work.
- Report mean and persistence baselines with every score. Persistence (test R^2 0.510, MAE 840) is within 0.07 R^2 of ridge and beats it on MAE; that caveat goes in the report.
- Keep `cnt_std_7` (sample std of `cnt` over d-7..d-1; `shift(1)` before `rolling(7)` on the calendar-reindexed series). Availability: every input is a count from d-7 to d-1, all known by the end of d-1, so nothing from day d goes in. Valid R^2 ridge 0.6475 -> 0.7224 (+0.075, MAE 833 -> 700), hgb 0.2368 -> 0.0964 (-0.140, MAE 1291 -> 1383); persistence 0.4507 and mean -0.9318 unchanged. 
- Kept: ridge was already a stronger model, and the feature substantially improves its validation R^2 and MAE, even though it degrades HGB's performance
- 2026-11-22: Residual target for HGB (Exercise 4): train on `cnt - cnt_lag_1`, add `cnt_lag_1` back. Defensible because yesterday's demand is available at prediction time. Valid R^2 / MAE on the count scale: hgb 0.0964 / 1382.9 -> hgb_residual 0.5714 / 870.6; ridge 0.7224 / 700.4; persistence 0.4507 / 900.6; mean -0.9318 / 2002.2. It substantially improves HGB but still underperforms ridge, so the original pipeline is retained. Validation only, test not scored; reproduce with `python -m src.train --residual-experiment`.
