# Baseline evaluation: who wins the race?

_Generated 2026-10-08 by `python3 -m evaluation.run`. Walk-forward: each race is predicted using only earlier races._

## Data

- 189 race weekends loaded; **174 evaluated** (2018 R16 → 2026 R16); the first 15 are training warm-up.
- 2018: 21 races
- 2019: 21 races
- 2020: 17 races
- 2021: 22 races
- 2022: 22 races
- 2023: 22 races
- 2024: 24 races
- 2025: 24 races
- 2026: 16 races

## Results (95% bootstrap CI over races in brackets)

| Model | Winner = top pick | Winner in top 3 | Winner's avg rank | Log loss ↓ | Brier ↓ |
|---|---|---|---|---|---|
| `uniform` | 0.0% [0–0] | 9.2% [5–14] | 9.66 [9.04–10.29] | 3.004 [3.000–3.008] | 0.950 [0.950–0.951] |
| `grid_prior` | 54.0% [47–61] | 87.9% [83–93] | 2.39 [1.97–2.84] | 1.532 [1.337–1.741] | 0.651 [0.602–0.704] |
| `form_only` | 46.6% [40–54] | 75.9% [70–82] | 2.49 [2.20–2.80] | 1.585 [1.418–1.745] | 0.684 [0.615–0.751] |
| `grid_plus_form` | 55.2% [48–63] | 90.2% [86–94] | 1.91 [1.70–2.14] | 1.235 [1.090–1.395] | 0.574 [0.510–0.644] |

`grid_prior` always picks the pole sitter, so its 'top pick' rate is the **'pole sitter wins' baseline**. Log loss of `uniform` is ln(≈20) ≈ 3.0; lower is better.

## Paired difference in log loss vs `grid_prior` (negative = better)

- `uniform`: +1.472 [+1.264, +1.669] → **worse**
- `form_only`: +0.053 [-0.191, +0.303] → **not distinguishable**
- `grid_plus_form`: -0.297 [-0.448, -0.156] → **better**

## Calibration of `grid_plus_form` (pooled over all drivers)

| Predicted bucket | Driver-races | Mean predicted | Observed win rate |
|---|---|---|---|
| 0–2% | 2585 | 0.4% | 0.1% |
| 2–5% | 313 | 3.2% | 2.6% |
| 5–10% | 201 | 7.0% | 6.0% |
| 10–20% | 151 | 14.0% | 16.6% |
| 20–35% | 97 | 27.2% | 33.0% |
| 35–50% | 78 | 41.6% | 43.6% |
| 50–100% | 85 | 70.5% | 70.6% |

A well-calibrated model has 'predicted' ≈ 'observed' in every bucket. Small samples make rare buckets noisy.

