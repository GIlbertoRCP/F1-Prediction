# Championship simulation: how well does it work?

_Walk-forward: for each of 5 past seasons (2021–2025) and every round from 3 on, the rest of the season is simulated (1000 runs) from results through that round only, then compared with how the season really finished. Each season counts only once as a title outcome, so the title numbers below rest on five champions per cutoff; the points-range numbers have far more data._

## Choosing the one fitted number (`TAU`, the size of the pace drift allowed in a season)

| TAU | 80% range covers actual points | MAE of expected points | MAE of straight-line projection | log loss on champion | log loss on constructors' champion |
|---|---|---|---|---|---|
| 0.00 | 63% (1582) | 22.5 | 23.0 | 0.684 | 0.760 |
| 0.30 | 67% (1582) | 22.5 | 23.0 | 0.581 | 0.645 |
| 0.60 | 73% (1582) | 22.4 | 23.0 | 0.500 | 0.563 |
| 0.80 | 78% (1582) | 22.4 | 23.0 | 0.485 | 0.517 |
| 0.90 | 80% (1582) | 22.4 | 23.0 | 0.487 | 0.499 |
| 1.00 | 82% (1582) | 22.5 | 23.0 | 0.490 | 0.485 |
| 1.20 | 85% (1582) | 22.7 | 23.0 | 0.507 | 0.475 |

A well-calibrated 80% range covers about 80%. A larger TAU widens the ranges; too small a TAU makes the simulation overconfident because it assumes every car keeps exactly its current pace.

Chosen: **TAU = 0.90**.

## Per season at the chosen TAU

| Season | 80% range coverage | MAE expected pts | MAE straight-line | log loss on champion |
|---|---|---|---|---|
| 2021 | 86% | 18.2 | 18.2 | 1.007 |
| 2022 | 79% | 21.2 | 17.6 | 0.169 |
| 2023 | 79% | 23.1 | 29.2 | 0.014 |
| 2024 | 69% | 29.0 | 29.8 | 0.231 |
| 2025 | 86% | 20.1 | 20.2 | 0.989 |

## Against a simple rival

Straight-line projection of each driver's points, plus random noise that grows with the races left (noise level picked in hindsight, which flatters it): log loss on the eventual champion **0.523** at 12 points of noise per √race, versus **0.487** for the simulation. Lower is better.

| Points of noise per √race | Log loss on champion |
|---|---|
| 3 | 1.075 |
| 5 | 0.805 |
| 8 | 0.598 |
| 12 | 0.523 |
| 18 | 0.526 |

## Do title odds mean what they say? (all cutoffs, all seasons)

| Predicted title chance | Driver-cutoffs | Mean predicted | Won the title |
|---|---|---|---|
| 0%–2% | 1862 | 0.0% | 0.0% |
| 2%–10% | 60 | 4.7% | 1.7% |
| 10%–30% | 42 | 19.4% | 31.0% |
| 30%–60% | 42 | 44.7% | 50.0% |
| 60%–90% | 39 | 75.2% | 64.1% |
| 90%–100% | 40 | 97.8% | 97.5% |

Cutoffs within a season are strongly correlated, so these frequencies rest on far fewer independent outcomes than the row counts suggest (5 champions).

## Known limits

- Fastest-lap bonus points (scored through 2024) are not simulated; they are in the actual totals, so the backtest slightly understates the points of the front-runners.
- Everyone in the latest race's line-up is assumed to start every remaining round; injuries and replacements are not forecast.
- Form is frozen at the cutoff; the TAU drift stands in for upgrades and development.
- Selection effects: TAU was chosen so the 80% ranges hit 80% on these same seasons, and the two recent-points memory lengths (3 and 6 races) were chosen among a handful of variants on them too. The coverage figure is a fit, not a test; the comparisons with the straight-line rival are mildly flattering for the same reason.
