# Practice pace: does it help?

_Walk-forward. Practice data starts at 2022 R1; 107 weekends have it (99% of the era). Warm-up: 30 weekends. **77 races scored**, identical for every model (2023 R9 to 2026 R16)._

## Results

| Model | Uses the grid? | Winner = top pick | Winner in top 3 | Log loss ↓ |
|---|---|---|---|---|
| `grid_plus_form_all` | yes | 59.7% [48–70] | 93.5% [87–99] | 1.133 [0.929, 1.375] |
| `grid_plus_form_tele` | yes | 59.7% [48–70] | 90.9% [84–97] | 1.188 [0.938, 1.496] |
| `grid_form_fp` | yes | 55.8% [45–66] | 87.0% [79–95] | 1.243 [0.978, 1.551] |
| `grid_form_fp_form` | yes | 55.8% [44–66] | 88.3% [81–95] | 1.256 [0.998, 1.567] |
| `pre_form_only` | no | 39.0% [29–49] | 70.1% [60–81] | 1.693 [1.422, 1.984] |
| `pre_quali_fp` | no | 36.4% [26–48] | 71.4% [61–82] | 1.664 [1.381, 1.962] |
| `pre_quali_fp_form` | no | 36.4% [26–48] | 64.9% [55–75] | 1.681 [1.412, 1.966] |

## Paired log-loss difference vs `grid_plus_form_tele` (the same model without practice data, trained on the same window); negative = better

- `grid_plus_form_all`: -0.055 [-0.143, +0.016] → **not distinguishable**
- `grid_form_fp`: +0.055 [+0.004, +0.108] → **worse**
- `grid_form_fp_form`: +0.068 [+0.013, +0.132] → **worse**

## Paired log-loss difference vs `grid_plus_form_all` (the production model (all history)); negative = better

- `grid_plus_form_tele`: +0.055 [-0.016, +0.144] → **not distinguishable**
- `grid_form_fp`: +0.110 [+0.016, +0.217] → **worse**
- `grid_form_fp_form`: +0.123 [+0.029, +0.232] → **worse**
- `pre_form_only`: +0.560 [+0.333, +0.777] → **worse**
- `pre_quali_fp`: +0.531 [+0.315, +0.729] → **worse**
- `pre_quali_fp_form`: +0.548 [+0.332, +0.754] → **worse**

## Before qualifying: how much does practice pace buy?

- `pre_quali_fp` vs `pre_form_only` (same inputs minus practice pace): -0.029 [-0.126, +0.075] → **not distinguishable**
- `pre_quali_fp_form` vs `pre_form_only` (same inputs minus practice pace): -0.012 [-0.103, +0.088] → **not distinguishable**

For scale: a forecast made after qualifying (`grid_plus_form_tele`) scores +0.476 log loss better than the best pre-qualifying model (negative means the pre-qualifying model is ahead).

### Calibration of `pre_quali_fp` (pre-qualifying)

| Predicted bucket | Driver-races | Mean predicted | Observed |
|---|---|---|---|
| 0–2% | 1144 | 0.2% | 0.3% |
| 2–5% | 107 | 3.3% | 4.7% |
| 5–10% | 120 | 7.2% | 10.8% |
| 10–20% | 82 | 14.5% | 18.3% |
| 20–35% | 61 | 27.0% | 23.0% |
| 35–50% | 27 | 41.2% | 22.2% |
| 50–100% | 29 | 78.6% | 69.0% |

Seven models were compared on the same races, so the best-looking one is mildly flattered by selection.

