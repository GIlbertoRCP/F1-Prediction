# Baseline evaluation: who wins the race?

_Generated 2026-10-08 by `python3 -m evaluation.run`. Walk-forward: each race is predicted using only earlier races._

## Data

- 39 race weekends loaded; **24 evaluated** (2024 R11 → 2026 R7); the first 15 are training warm-up.
- 2023: 5 races, missing rounds [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]
- 2024: 18 races, missing rounds [14, 15, 16, 17, 18, 19]
- 2025: 9 races, missing rounds [4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
- 2026: 7 races

> **Caution:** the dataset has gaps, so 'recent form' skips races and the numbers below are indicative only. Run `python3 scripts/fetch_results.py` to download complete history, then re-run.


## Results (95% bootstrap CI over races in brackets)

| Model | Winner = top pick | Winner in top 3 | Winner's avg rank | Log loss ↓ | Brier ↓ |
|---|---|---|---|---|---|
| `uniform` | 0.0% [0–0] | 20.8% [4–38] | 11.38 [9.29–13.46] | 3.024 [3.008–3.043] | 0.951 [0.951–0.952] |
| `grid_prior` | 58.3% [38–79] | 87.5% [75–100] | 2.79 [1.38–4.83] | 1.474 [1.006–2.081] | 0.620 [0.488–0.764] |
| `form_only` | 37.5% [17–58] | 66.7% [46–83] | 2.88 [2.12–3.67] | 1.864 [1.618–2.139] | 0.829 [0.732–0.932] |
| `grid_plus_form` | 54.2% [33–75] | 87.5% [75–100] | 1.92 [1.46–2.42] | 1.319 [0.990–1.684] | 0.623 [0.468–0.785] |

`grid_prior` always picks the pole sitter, so its 'top pick' rate is the **'pole sitter wins' baseline**. Log loss of `uniform` is ln(≈20) ≈ 3.0; lower is better.

## Paired difference in log loss vs `grid_prior` (negative = better)

- `uniform`: +1.549 [+0.936, +2.023] → **worse**
- `form_only`: +0.389 [-0.267, +0.897] → **not distinguishable**
- `grid_plus_form`: -0.155 [-0.489, +0.107] → **not distinguishable**

## Calibration of `grid_plus_form` (pooled over all drivers)

| Predicted bucket | Driver-races | Mean predicted | Observed win rate |
|---|---|---|---|
| 0–2% | 355 | 0.3% | 0.0% |
| 2–5% | 38 | 3.7% | 5.3% |
| 5–10% | 38 | 6.6% | 2.6% |
| 10–20% | 25 | 14.5% | 16.0% |
| 20–35% | 20 | 27.1% | 30.0% |
| 35–50% | 6 | 41.3% | 66.7% |
| 50–100% | 12 | 61.8% | 58.3% |

A well-calibrated model has 'predicted' ≈ 'observed' in every bucket. Small samples make rare buckets noisy.

