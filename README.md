# F1 Winner Oracle

**Calibrated Formula 1 race-winner probabilities, with a public track record that can't be quietly edited.**

[Live site](https://gilbertorcp.github.io/F1-Prediction/) · [Model card](MODEL_CARD.md) · [Evaluation reports](reports/)

Most F1 prediction projects show a pick and a screenshot of a good race. This one is built around the harder
question: *when it says 30%, does that happen about 30% of the time?* Every forecast is frozen before the lights
go out, written to a tamper-evident log, and scored in public, including the misses.

It is a static site. Fans open a link and use everything in the browser; a scheduled GitHub Action keeps it current.
Nobody has to run a script.

## What you can do on the site

* **Forecast.** After qualifying, win odds for every driver, frozen and fingerprinted. Make your own pick and
  compare your score against the model's (stored in your browser only).
* **Race simulator.** Move the starting grid or take a driver out, and the race is re-run thousands of times in
  your browser: win, podium and average finish for every driver.
* **Championship.** Title odds for drivers and constructors from a simulation of the races and sprints left,
  how those odds moved over the season, and how far to trust them.
* **Standings and head to head.** Season standings with points charts, teammate battles and any two drivers compared,
  counted from real results.
* **Track record.** Calibration chart, season-by-season results, a live record kept separately from replays, and
  every race forecast ever made.

## What the numbers say (174 races, walk-forward)

| | Top pick wins | Log loss (lower is better) |
|---|---|---|
| Random guess | 0% | 3.00 |
| Pole sitter always wins | 54.0% | 1.53 |
| **Winner Oracle** | **55.2%** | **1.24** |

The model beats the grid-only baseline on log loss (paired 95% interval -0.45 to -0.16) and its probabilities
are close to calibrated. As a single pick it is **no better than the pole sitter**. What it adds is honest odds for
everyone else. That is stated on the site, not hidden.

I also tested the ideas people usually assume help, and reported the ones that did not:

* **Qualifying pace** adds nothing once the grid is known.
* **Practice-session pace** (107 weekends of lap data) makes the forecast slightly worse, and gives no measurable
  gain for a pre-qualifying forecast. Without a grid, the top pick is right about 36-39% of the time against about 60% with one.
* **My original XGBoost ranker** on engineered telemetry features scored worse than the simple model on the races
  it was run on. It is archived, not deleted.
* **A joint ten-place model** hurt the win odds, so the finishing-order extension keeps the win odds exactly and adds
  the later places separately.

Full detail, with confidence intervals and caveats, is in the [model card](MODEL_CARD.md) and `reports/`.

## How it is built

```
Jolpica API ─► results.csv ─► features (built before each race) ─► conditional logit ─► probabilities
FastF1 ──────► practice laps, circuit outlines                                            │
                                                                                          ▼
GitHub Action (every 3 h, Fri-Mon) ─► freeze forecast ─► hash-chained log ─► site/data/*.json ─► static site
```

* **Model in plain Python.** A conditional logit with exponentially weighted driver and team form and the grid
  position, fitted by Newton's method with a backtracking line search. No numpy, no ML library, so it is easy to read
  and to audit.
* **Walk-forward everywhere.** Every race is predicted from earlier races only; features for a race are fixed before its
  result is added. A test checks that changing a future result cannot change an earlier feature.
* **Tamper-evident log.** Each live record stores the hash of the previous one. Editing or deleting history breaks the
  chain. The publisher refuses to log a forecast after a race has started or to overwrite an existing one, and git
  history is a second timestamp.
* **The simulator runs in the browser** using the model's exported parameters, and a Node test proves the JavaScript
  reproduces the Python win odds to within 2e-6.
* **Static, no build.** Plain HTML, CSS and ES modules reading JSON files; hosted on GitHub Pages.
* **85 tests** (68 Python, 17 JavaScript) cover the evaluation, the log, the simulators and the data code.

## Run it yourself

```bash
python3 scripts/fetch_results.py                 # results, qualifying, sprints, calendar (needs internet)
python3 -m evaluation.run                        # baselines and the model -> reports/baselines.md
python3 -m oracle.publish                        # freeze the forecast and rebuild site/data
cd site && python3 -m http.server 8000           # open http://localhost:8000
python3 -m unittest discover -s tests            # Python tests
node --test tests/*.test.mjs                     # JavaScript tests
```

The hosted site does not need any of this; the scheduled job in `.github/workflows/` does it.

## Repository tour

```
site/            the static site and its data files in site/data/
oracle/          forecast engine, prediction log, publishing, championship outlook, circuit outlines
evaluation/      walk-forward evaluation, models, finishing-order model, championship simulation, backtests
scripts/         data download (results, practice laps, circuit outlines)
data/            results, prediction logs (data/predictions), practice features, championship backtest
reports/         every evaluation, including the ideas that did not work
tests/           Python and JavaScript tests
archive/         the original XGBRanker, kept so its old predictions can still be scored
.github/         the jobs that keep the site current and draw the circuit outlines
```

## Limits worth knowing

* The live record is empty until the first live race is scored; today's accuracy numbers come from replays.
* Replays use the final starting grid (penalties included); live forecasts use the qualifying result at freeze time.
* Small samples: single seasons (6-24 races) and championship title odds (five champions) are rough.
* The model does not see weather, strategy, safety cars, reliability or mid-season changes, and it is weakest right
  after a regulation change.
* Not betting advice. Independent fan project, not affiliated with Formula 1, the FIA or any team.

## Data and credit

Results, qualifying and calendar data come from the [Jolpica-F1](https://github.com/jolpica/jolpica-f1) API (the
maintained successor to Ergast). Practice laps and circuit outlines come from [FastF1](https://github.com/theOehrly/Fast-F1).
Thanks to both projects.

---

## Reference: how each part works

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
