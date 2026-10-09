# F1 Winner Oracle

Calibrated Formula 1 race-winner probabilities with a public track record, plus a championship simulator,
a race simulator, standings and head-to-head. A static site on GitHub Pages: nothing to install or run for
anyone who just wants to use it. _(A full write-up and model card will replace this page once the project is done.)_

## Project structure

```
site/            the static site (plain HTML/CSS/JS, no build) and its data files in site/data/
oracle/          the product: forecast engine, tamper-evident prediction log, publishing, championship outlook
evaluation/      walk-forward evaluation, models, ordered-finish model, championship simulation, backtests
scripts/         data download (results, practice laps, circuit outlines)
data/            results, the prediction logs (data/predictions), practice features, championship backtest
reports/         every evaluation, including the ideas that did not work
tests/           Python and JavaScript tests
archive/         the original XGBRanker model, kept only so its old predictions can still be scored
.github/         the jobs that keep the site current and draw the circuit outlines
```

## Winner Oracle (the product)

Calibrated win probabilities for each race, frozen before the start and scored in public.

```bash
python3 scripts/fetch_results.py --from 2026     # new results, qualifying, calendar (needs internet)
python3 -m oracle.publish                        # freeze the forecast for the upcoming race, rebuild site/data
cd site && python3 -m http.server 8000           # static front page at http://localhost:8000
```

- `oracle/engine.py` is the model (`grid_plus_form`, the backtest winner). `oracle/store.py` is the prediction log: `data/predictions/live.jsonl` is append-only and hash-chained (editing or deleting a record breaks the chain), `backtest.jsonl` holds clearly labelled replays.
- `publish` refuses to log a forecast once the race has started, and never overwrites an existing live forecast.
- `evaluation/ordered.py` extends the model to the whole finishing order (win odds unchanged; exact podium odds; Monte Carlo). `site/sim.js` runs it in the browser for the race simulator, and `tests/sim.test.mjs` checks it reproduces the Python numbers. `reports/ordered.md` shows how well podium and top-10 odds are calibrated, including the variants that did not work.
- On GitHub the update job commits the prediction logs after each run, so the git history is a second, independent timestamp.

### Championship simulation

`evaluation/season.py` plays out the rest of a season (races and sprints left, from the calendar) thousands of times from a form-only model and counts who takes the drivers' and constructors' titles. `python3 -m evaluation.season_eval` replays 2021–2025 round by round, writes `reports/championship.md` and `data/championship_history.json`, and is how its one fitted number (`TAU`, allowed pace drift) was chosen. `oracle/championship.py` builds `site/data/championship.json` and logs each live forecast to `data/predictions/championship_live.jsonl` (same hash chain as the race log).

### Circuit outlines

`uv run python scripts/extract_circuits.py` draws each circuit from real car positions (one fast qualifying lap from FastF1) into `site/data/circuits.json`. Resumable; the site shows no map for circuits that are missing.

### Does practice pace help? (the telemetry test)

Practice sessions finish before qualifying, so their pace is legitimately known before any grid exists. `scripts/extract_practice_features.py` turns FastF1 practice laps into one row per driver per weekend (best clean-lap gap, same-compound long-run gap) in `data/telemetry/practice_features.csv`; it is resumable and logs failures to `errors.log`. `python3 -m evaluation.telemetry_eval --out reports/telemetry.md` then scores every model on the identical races with paired log-loss differences, and also tests a pre-qualifying forecast. Nothing is claimed until that report exists from real data.

```bash
uv run python scripts/extract_practice_features.py --from 2022 --to 2026 --limit 1   # smoke test
uv run python scripts/extract_practice_features.py --from 2022 --to 2026             # full, resumable
python3 -m evaluation.telemetry_eval --out reports/telemetry.md
```

## Evaluation: does the model beat simple baselines?

Predictions are scored **walk-forward**: every race is predicted using only earlier races, so nothing leaks from the future (this is unit-tested). Metrics are how often the top pick wins, where the actual winner ranked, log loss / Brier score for the win probabilities, and calibration, with bootstrap confidence intervals.

```bash
python3 scripts/fetch_results.py          # one-off: download 2018 to now (needs internet, no dependencies)
python3 -m evaluation.run                 # baselines -> reports/baselines.md
python3 -m evaluation.run --predictions my_model.csv   # also score your own model
python3 -m unittest discover -s tests     # run the tests
```

`--predictions` expects a CSV with columns `season, round, driver_id, win_prob`. Baselines: uniform, a grid-slot prior ("the pole sitter wins"), team/driver form only, and grid plus form.

### The original XGBRanker, scored against the same baselines

The first version of the project (an XGBoost ranker on engineered telemetry features) is archived in `archive/xgb_ranker/`. Its 2026 predictions are kept in `data/model_scores/` and can still be scored with:

```bash
python3 -m evaluation.run --scores fixed=data/model_scores/xgb_ranker_2026.csv legacy=data/model_scores/xgb_ranker_2026_legacy.csv
```

See `reports/baselines.md` for how it compares. The sprint-weekend detection bug that "legacy" reproduces is described in `archive/xgb_ranker/OLD_README.md`.
