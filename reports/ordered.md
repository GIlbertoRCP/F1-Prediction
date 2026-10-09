# Rank-ordered model: finishing-order probabilities

_Walk-forward over 174 races; podium and top-10 odds from 600 simulated races each._

## Win probabilities (log loss, lower is better)

| Model | Log loss | vs `winner_only` (paired, 95% CI) |
|---|---|---|
| `winner_only` | 1.235 [1.090, 1.395] | – |
| `exploded_3` | 1.276 [1.151, 1.415] | +0.041 [-0.011, +0.090] → not distinguishable |
| `exploded_10` | 1.503 [1.415, 1.600] | +0.267 [+0.188, +0.339] → worse |
| `scaled_pl` | 1.235 [1.090, 1.395] | +0.000 [+0.000, +0.000] → not distinguishable |

## Podium (top 3): calibration

### `exploded_3` (mean squared error per driver: 0.0677)

| Predicted bucket | Driver-races | Mean predicted | Observed |
|---|---|---|---|
| 0–2% | 1521 | 0.9% | 0.3% |
| 2–5% | 617 | 3.1% | 1.8% |
| 5–10% | 279 | 7.1% | 5.4% |
| 10–20% | 297 | 14.5% | 15.2% |
| 20–35% | 250 | 26.1% | 32.8% |
| 35–50% | 159 | 41.9% | 48.4% |
| 50–100% | 387 | 76.2% | 74.2% |

### `exploded_10` (mean squared error per driver: 0.0718)

| Predicted bucket | Driver-races | Mean predicted | Observed |
|---|---|---|---|
| 0–2% | 327 | 1.4% | 0.3% |
| 2–5% | 1180 | 3.3% | 0.3% |
| 5–10% | 686 | 6.9% | 2.2% |
| 10–20% | 477 | 14.3% | 10.5% |
| 20–35% | 380 | 26.7% | 32.9% |
| 35–50% | 201 | 41.9% | 60.7% |
| 50–100% | 259 | 68.4% | 79.2% |

### `scaled_pl` (mean squared error per driver: 0.0689)

| Predicted bucket | Driver-races | Mean predicted | Observed |
|---|---|---|---|
| 0–2% | 1302 | 1.1% | 0.3% |
| 2–5% | 722 | 3.1% | 1.4% |
| 5–10% | 370 | 7.1% | 3.8% |
| 10–20% | 342 | 14.5% | 15.8% |
| 20–35% | 259 | 26.6% | 35.9% |
| 35–50% | 155 | 42.4% | 49.7% |
| 50–100% | 360 | 76.2% | 75.0% |


## Top 10: calibration

### `exploded_3` (mean squared error per driver: 0.1630)

| Predicted bucket | Driver-races | Mean predicted | Observed |
|---|---|---|---|
| 0–2% | 3 | 1.8% | 0.0% |
| 2–5% | 122 | 3.9% | 2.5% |
| 5–10% | 349 | 7.6% | 6.0% |
| 10–20% | 613 | 14.8% | 17.1% |
| 20–35% | 593 | 26.6% | 35.8% |
| 35–50% | 328 | 41.9% | 53.0% |
| 50–100% | 1502 | 88.1% | 81.6% |

### `exploded_10` (mean squared error per driver: 0.1633)

| Predicted bucket | Driver-races | Mean predicted | Observed |
|---|---|---|---|
| 5–10% | 49 | 8.3% | 4.1% |
| 10–20% | 602 | 15.6% | 8.3% |
| 20–35% | 926 | 26.9% | 27.2% |
| 35–50% | 490 | 41.9% | 52.4% |
| 50–100% | 1443 | 82.3% | 81.7% |

### `scaled_pl` (mean squared error per driver: 0.1702)

| Predicted bucket | Driver-races | Mean predicted | Observed |
|---|---|---|---|
| 10–20% | 182 | 17.5% | 3.3% |
| 20–35% | 1282 | 27.7% | 20.0% |
| 35–50% | 700 | 41.3% | 51.1% |
| 50–100% | 1346 | 79.0% | 83.2% |

