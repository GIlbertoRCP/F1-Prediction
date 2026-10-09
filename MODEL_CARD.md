# Model card: F1 Winner Oracle

A model card in the style of Mitchell et al. (2019). Every number below comes from a report in `reports/` that
`python3 -m evaluation.run` (and the other evaluation scripts) regenerate from the data in `data/`. Nothing here is
estimated by hand. Where a result is weak or flattering, it says so.

## 1. Model details

| | |
|---|---|
| Name | `grid_plus_form`, served by `oracle/engine.py` |
| Author | Gilberto Romero-Cano |
| Type | Conditional (multinomial) logit: one race is a choice set, the winner is the choice |
| Question it answers | Given the starting grid and recent form, how likely is each driver to win this Grand Prix? |
| Inputs (5 features) | `log_grid` (log of the starting slot); `team_score` and `driver_score` (exponentially weighted finishing score, 1.0 for a win down to 0.0 for last or not classified); `driver_win` and `team_win` (exponentially weighted share of recent wins) |
| Form memory | Half-life of 6 appearances for every exponentially weighted feature |
| Fitting | Penalised maximum likelihood (L2 = 1) by Newton's method with backtracking line search, written in plain Python. No numpy, no ML library |
| Output | A probability for every driver; the probabilities sum to 100% |
| Extensions | `ScaledPL` extends the same model to a whole finishing order: the winner odds are unchanged, and one fitted "sharpness" scale per later place gives exact podium odds and a Monte Carlo of full races. The race simulator on the site runs this in the browser |
| Version | Each prediction stores `model_version`, a hash of `evaluation/models.py`, `evaluation/ordered.py` and `oracle/engine.py` |
| Latest fitted weights | `log_grid` -1.03, `driver_score` +0.90, `team_score` +0.43, `driver_win` +0.20, `team_win` -0.13 (on standardised features). The small negative `team_win` is the model sharing credit with the correlated `driver_win`, not a real penalty for winning teams |

Two further models sit on top of the same ingredients:

* **Championship simulation** (`evaluation/season.py`): plays out the remaining races and sprints of a season from a
  form-only version of the ordered model (no grid, because future grids are unknown) plus recent-points features.
  It adds a seasonal pace-drift term (`TAU = 0.90`) fitted on 2021-2025 replays.
* **Race simulator** (browser): re-runs a race from the exported model, so a visitor can move the grid or take a driver out.

## 2. Intended use

* **Primary:** show fans how likely each driver is to win a race once the grid is set, and keep an honest, public
  record of how those probabilities performed.
* **Also fine:** learning about calibration and walk-forward evaluation; comparing your own picks against the model
  (picks are stored in your own browser only).
* **Not intended:** betting or any financial decision, predicting a single driver's skill or career, safety or
  engineering decisions. The probabilities describe how often drivers in similar situations have won, not what will
  happen on Sunday. They are not betting advice.

## 3. Factors that matter for the results

* **How open the season is.** Accuracy swings a lot from year to year. The top pick won 86% of races in 2023 (one
  dominant car) but 36% in 2022 and 46% in 2024. Per-season numbers rest on 6 to 24 races and are rough.
* **Grid position** is the strongest input by far. When the best car does not start at the front, the model is
  more spread out and less sure.
* **What the model does not see:** weather, tyres and strategy, safety cars, reliability, penalties announced after
  the grid is frozen, driver changes mid-season, regulation changes. After a rule change (2022, 2026) the first races
  lean on form from a different era.

## 4. Metrics

* **Log loss** of the probability given to the real winner: the main score. It rewards honest confidence and punishes
  confident misses. A uniform guess over about 20 drivers scores 3.00.
* **Brier score**, **top pick wins**, **winner in the top three**, and the **average probability given to the winner**.
* **Calibration:** when the model says 30%, does it happen about 30% of the time?
* **Uncertainty:** 95% bootstrap intervals over races, and paired log-loss differences between models on the same
  races. Because differences are paired, a model is only called better or worse when its interval excludes zero.

## 5. Evaluation and training data

* **Source:** race results, qualifying, sprint results and the calendar from the Jolpica-F1 API (the maintained
  successor to the Ergast API), 2018 to 2026 round 16: 189 race weekends. Practice laps and circuit outlines come
  from FastF1.
* **Protocol:** walk-forward. Every race is predicted using only earlier races, and features for race *t* are built
  before race *t*'s result is added. The first 15 races are warm-up, so **174 races are scored (2018 R16 to 2026 R16)**.
  A unit test checks that changing a future result cannot change an earlier feature.
* **Selection caveat:** the feature set was chosen among a handful of variants on these same races, so the numbers
  are mildly flattering. Qualifying and practice features were tried and rejected, but that comparison used the same races too,
  so there is no untouched held-out set. The live record is the only fully clean test, and it is still empty.

## 6. Quantitative results

### Winner probabilities (174 races)

| Model | Top pick wins | Winner in top 3 | Log loss (lower is better) |
|---|---|---|---|
| Uniform guess | 0.0% | 9.2% | 3.004 |
| Pole sitter always wins (slot prior) | 54.0% | 87.9% | 1.532 |
| Recent form only, no grid | 46.6% | 75.9% | 1.585 |
| **`grid_plus_form` (this model)** | **55.2%** [47.7, 62.6] | **90.2%** [85.6, 94.2] | **1.235** [1.090, 1.395] |

* The model improves on the grid-only baseline by **0.297 log loss** (paired 95% interval -0.448 to -0.156).
* As a single best guess it is **no better than picking the pole sitter** (55.2% against 54.0%, intervals overlap
  heavily). What it adds is honest odds for everyone else: on average it gave the eventual winner 41% where a random
  guess gives about 5%.
* Recent form alone, with no grid, is not distinguishable from the grid-only baseline.

### Calibration (production model, all 174 races)

| Predicted chance | Driver-races | Mean predicted | Observed win rate |
|---|---|---|---|
| 0-2% | 2585 | 0.4% | 0.1% |
| 2-5% | 313 | 3.2% | 2.6% |
| 5-10% | 201 | 7.0% | 6.0% |
| 10-20% | 151 | 14.0% | 16.6% |
| 20-35% | 97 | 27.2% | 33.0% |
| 35-50% | 78 | 41.6% | 43.6% |
| 50-100% | 85 | 70.5% | 70.6% |

Close to the diagonal across the range. The model slightly **under-rates drivers in the 20-35% band** (33% observed
against 27% predicted) and slightly over-rates the very smallest chances. Each bucket's observed rate is noisy, and
rare buckets hold only about 80-100 driver-races.

### Finishing order (`reports/ordered.md`)

* Exact podium odds are decent but not perfect: the model under-rates mid-field drivers in the 20-50% band and over-rates
  long shots. Positions below third are rougher still, and the site says so beside the simulator.
* An "exploded logit" that fits places 1-10 jointly **hurt** the win odds (log loss 1.503 against 1.235), so it was
  rejected. `ScaledPL` keeps the win odds exactly and adds the later places, which is why it is used.

### Championship simulation (`reports/championship.md`)

* Replayed on 2021-2025 at every round (99 replays). Expected final points were off by **22.4** on average, against
  **23.0** for simply extending each driver's current points rate: a small gain.
* Title odds: log loss on the eventual champion **0.49**, against **0.52** for a plain projection whose noise was
  tuned in hindsight. A small edge on **five champions**, so title odds are the least certain output.
* The 80% final-points ranges hold 80% of real outcomes, but `TAU` was chosen to make that so on the same seasons.
  That coverage is a fit, not an independent test.
* Not modelled: upgrades, penalties, injuries.

### What was tried and did not help

| Idea | Result |
|---|---|
| Qualifying pace features (gap to the fastest lap, team best gap, qualifying position) | Not distinguishable from the grid alone (+0.013 and -0.004 log loss, both intervals include zero), so left out |
| Practice pace features, 107 weekends of FastF1 laps (`reports/telemetry.md`) | With the grid: slightly **worse** (+0.055, interval +0.004 to +0.108). Before qualifying: nothing measurable (-0.029, interval -0.126 to +0.075) |
| Forecast before qualifying (form only) | Much weaker: top pick right 36-39% of the time against about 60% once the grid is known, and about 0.48 log loss worse |
| Original XGBoost ranker on engineered telemetry features | Scored on the 11 races it was run on, it was **worse** than the simple model (paired +0.545 log loss, interval +0.208 to +0.880); archived in `archive/xgb_ranker/` |
| Joint ten-place "exploded" logit | Worse win odds, see above |

The pattern is the useful finding: once the starting grid is known, almost all the signal is already in the grid
and in recent results, and extra features add noise on a sample this size.

## 7. Ethical considerations

* Data is public sports results about professional drivers; no private data is used or stored. Picks are kept in the
  visitor's own browser only.
* Probabilities can be mistaken for certainty or for betting guidance. The site states that it is not betting advice
  and shows its own misses.
* The model rates results, which mix driver and car. A low chance for a driver is a statement about recent results
  from that seat, not about the person.
* This is an independent fan project, not affiliated with Formula 1, the FIA or any team.

## 8. Caveats and recommendations

* **No live record yet.** The first live forecast is frozen after qualifying for the next race; until live races are
  scored, every accuracy figure comes from replays.
* **Replays are not live forecasts.** A replay uses only earlier races but the final starting grid, including penalties.
  A live forecast uses the qualifying classification at the moment it is frozen, so a penalty announced afterwards
  can move the real grid. The two are kept in separate logs and labelled everywhere.
* **Small samples.** Per-season rows (6-24 races) and the championship title odds (five champions) have wide
  uncertainty. Do not read precision into them.
* **Non-stationary.** Regulation changes reset the pecking order; expect weaker forecasts at the start of a new era.
* **Sprint races** are not forecast. Races without a grid (cancelled or red-flagged restarts) are out of scope.
* **Recommendation:** read the probabilities as a calibrated view of the field, not as a pick. Check the live record
  before trusting any headline number.

## 9. Integrity and reproducibility

* Live forecasts are written to `data/predictions/live.jsonl`, an append-only log where every record carries the hash
  of the one before it. Editing or deleting a record breaks the chain and the site shows it. `publish` refuses to log a
  forecast after the race has started and never overwrites an existing one. The git history is a second, independent
  timestamp. Championship forecasts have their own chained log.
* Reproduce everything with `python3 scripts/fetch_results.py`, `python3 -m evaluation.run`,
  `python3 -m evaluation.ordered_eval`, `python3 -m evaluation.telemetry_eval` (needs the practice data) and
  `python3 -m evaluation.season_eval`. Tests: `python3 -m unittest discover -s tests` and `node --test tests/*.test.mjs`.
* A Node test checks that the JavaScript simulator reproduces the Python win odds to within 2e-6.
* **Maintenance:** a scheduled GitHub Action fetches results, freezes forecasts and rebuilds the site; the model
  version hash changes whenever the model code changes.
