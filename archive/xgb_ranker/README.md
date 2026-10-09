# Archived: the original XGBRanker model

This is the first version of the project: an XGBoost pairwise ranker built on hand-engineered telemetry
features (`f1-api/f1_fe.py`), with per-circuit characteristics in `circuit_profiles.json` and team
power-unit scores in `team_mappings.json`. Those two JSON files were set by hand, not measured, so nothing in
the current product uses them.

It is kept for one reason: `data/model_scores/xgb_ranker_2026*.csv` holds this model's 2026 predictions, and
`python3 -m evaluation.run --scores data/model_scores/xgb_ranker_2026.csv` scores them against the current
model and the simple baselines (see `reports/baselines.md`). The code here is not maintained and is not
needed to run the site. `export_model_scores.py` and `f1_model.py` expect to be run from this folder's
original layout and may need path fixes; they are not part of the test suite.

The full original project, including its React dashboard, is still on the `main` branch.
