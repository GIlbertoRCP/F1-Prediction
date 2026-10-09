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
| `grid_form_qgap` | 54.6% [47–62] | 90.2% [86–94] | 1.92 [1.71–2.16] | 1.248 [1.098–1.410] | 0.577 [0.512–0.646] |
| `grid_form_quali` | 58.6% [51–66] | 90.8% [86–95] | 1.85 [1.65–2.09] | 1.231 [1.085–1.392] | 0.577 [0.511–0.647] |

`grid_prior` always picks the pole sitter, so its 'top pick' rate is the **'pole sitter wins' baseline**. Log loss of `uniform` is ln(≈20) ≈ 3.0; lower is better.

## Paired difference in log loss vs `grid_prior` (negative = better)

- `uniform`: +1.472 [+1.264, +1.669] → **worse**
- `form_only`: +0.053 [-0.191, +0.303] → **not distinguishable**
- `grid_plus_form`: -0.297 [-0.448, -0.156] → **better**
- `grid_form_qgap`: -0.283 [-0.430, -0.142] → **better**
- `grid_form_quali`: -0.301 [-0.460, -0.151] → **better**

## Does qualifying pace help? Paired log-loss difference vs `grid_plus_form` (negative = better)

- `grid_form_qgap`: +0.013 [-0.013, +0.048] → **not distinguishable**
- `grid_form_quali`: -0.004 [-0.042, +0.034] → **not distinguishable**

Two qualifying variants were tried, so the better-looking one is mildly flattered by selection.

## Calibration of `grid_form_quali` (pooled over all drivers)

| Predicted bucket | Driver-races | Mean predicted | Observed win rate |
|---|---|---|---|
| 0–2% | 2597 | 0.4% | 0.1% |
| 2–5% | 304 | 3.2% | 2.3% |
| 5–10% | 207 | 7.2% | 8.2% |
| 10–20% | 142 | 14.3% | 15.5% |
| 20–35% | 90 | 27.3% | 28.9% |
| 35–50% | 76 | 41.6% | 44.7% |
| 50–100% | 94 | 67.5% | 69.1% |

A well-calibrated model has 'predicted' ≈ 'observed' in every bucket. Small samples make rare buckets noisy.


## Your ranker vs the baselines

Score file(s): `fixed_only`. 15 races have scores in every file; the first 4 are used only to fit the score→probability mapping, the rest are evaluated. Every row below is scored on the **same races**. Treat conclusions as provisional: samples this small give wide intervals.

### All evaluated scored races (11 races)

These races were available to the author while the model's hand-set constants (power-unit ratings, upgrade scores, grid-anchor weight) were chosen, so they may be flattering.

| Model | Winner = top pick | Winner in top 3 | Winner's avg rank | Log loss ↓ | Brier ↓ |
|---|---|---|---|---|---|
| `uniform` | 0.0% [0–0] | 36.4% [9–64] | 11.18 [7.55–15.09] | 3.091 [3.091–3.091] | 0.955 [0.955–0.955] |
| `grid_prior` | 63.6% [36–91] | 90.9% [73–100] | 2.45 [1.09–4.82] | 1.498 [0.722–2.751] | 0.552 [0.349–0.785] |
| `form_only` | 27.3% [0–55] | 72.7% [45–91] | 3.45 [2.27–4.82] | 1.998 [1.734–2.266] | 0.851 [0.765–0.932] |
| `grid_plus_form` | 63.6% [36–91] | 90.9% [73–100] | 2.09 [1.18–3.45] | 1.307 [0.847–1.917] | 0.576 [0.397–0.791] |
| `grid_form_qgap` | 63.6% [36–91] | 90.9% [73–100] | 2.09 [1.18–3.45] | 1.277 [0.843–1.848] | 0.569 [0.392–0.781] |
| `grid_form_quali` | 63.6% [36–91] | 90.9% [73–100] | 2.00 [1.09–3.27] | 1.204 [0.795–1.705] | 0.558 [0.361–0.789] |
| `fixed_only_only` | 45.5% [18–73] | 72.7% [45–100] | 2.91 [1.55–4.73] | 1.852 [1.392–2.435] | 0.750 [0.632–0.866] |
| `grid_form_plus_fixed_only` | 63.6% [36–91] | 81.8% [55–100] | 2.18 [1.18–3.55] | 1.326 [0.771–2.090] | 0.564 [0.362–0.804] |

Paired log-loss difference vs `grid_prior` (negative = better):
- `fixed_only_only`: +0.354 [-0.428, +0.942] → **not distinguishable**
- `grid_form_plus_fixed_only`: -0.172 [-0.763, +0.239] → **not distinguishable**

Paired log-loss difference vs `grid_plus_form` (negative = better):
- `fixed_only_only`: +0.545 [+0.208, +0.880] → **worse**
- `grid_form_plus_fixed_only`: +0.019 [-0.098, +0.184] → **not distinguishable**

Fitted weight on the score at the last race (0 = ignored; larger = trusted more): `fixed_only_only` β=1.93 (from 14 earlier races), `grid_form_plus_fixed_only` β=0.34 (from 14 earlier races)

### Clean holdout: races on/after 2026-06-17 (9 races)

Races after the model code was last edited (2026-06-17), so nothing was tuned on them. This is the fairest test of the model as it stands.

| Model | Winner = top pick | Winner in top 3 | Winner's avg rank | Log loss ↓ | Brier ↓ |
|---|---|---|---|---|---|
| `uniform` | 0.0% [0–0] | 33.3% [11–67] | 12.11 [7.56–16.33] | 3.091 [3.091–3.091] | 0.955 [0.955–0.955] |
| `grid_prior` | 66.7% [33–89] | 88.9% [67–100] | 2.67 [1.11–5.67] | 1.594 [0.736–3.213] | 0.543 [0.359–0.827] |
| `form_only` | 22.2% [0–56] | 66.7% [33–89] | 3.78 [2.33–5.33] | 2.052 [1.741–2.357] | 0.862 [0.762–0.947] |
| `grid_plus_form` | 66.7% [33–89] | 88.9% [67–100] | 2.11 [1.11–3.78] | 1.343 [0.825–2.122] | 0.576 [0.384–0.811] |
| `grid_form_qgap` | 66.7% [33–89] | 88.9% [67–100] | 2.11 [1.11–3.78] | 1.309 [0.815–2.046] | 0.568 [0.378–0.803] |
| `grid_form_quali` | 66.7% [33–89] | 88.9% [67–100] | 2.00 [1.11–3.67] | 1.212 [0.760–1.825] | 0.552 [0.348–0.802] |
| `fixed_only_only` | 44.4% [11–78] | 66.7% [33–100] | 3.11 [1.44–5.56] | 1.904 [1.361–2.704] | 0.756 [0.615–0.905] |
| `grid_form_plus_fixed_only` | 66.7% [33–89] | 77.8% [44–100] | 2.22 [1.11–4.00] | 1.379 [0.754–2.360] | 0.566 [0.352–0.839] |

Paired log-loss difference vs `grid_prior` (negative = better):
- `fixed_only_only`: +0.310 [-0.691, +1.016] → **not distinguishable**
- `grid_form_plus_fixed_only`: -0.215 [-0.963, +0.302] → **not distinguishable**

Paired log-loss difference vs `grid_plus_form` (negative = better):
- `fixed_only_only`: +0.561 [+0.140, +0.961] → **worse**
- `grid_form_plus_fixed_only`: +0.036 [-0.105, +0.263] → **not distinguishable**

Fitted weight on the score at the last race (0 = ignored; larger = trusted more): `fixed_only_only` β=1.93 (from 14 earlier races), `grid_form_plus_fixed_only` β=0.34 (from 14 earlier races)
