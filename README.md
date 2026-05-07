# 🏎️ F1 Race Prediction Pipeline — 2026 Season

> Machine learning pipeline for predicting Formula 1 race results using telemetry-based feature engineering via [FastF1](https://theoehrly.github.io/Fast-F1/) and an `XGBRanker` pairwise ranking model.

---

## 📁 Project Structure

```
f1/
├── f1-api/
│   └── f1_fe.py              # Feature Engineering Library (core)
├── miami/
│   └── miami_model.py        # Miami 2026 Race Prediction Model
├── team_mappings.json         # PU scores & works team flags
├── f1_cache/                  # FastF1 local telemetry cache
└── README.md
```

---

## 🔬 Feature Engineering Library — `f1_fe.py`

The library exposes **pure functions** that each return a `pd.DataFrame` indexed by `Driver`. All functions share these design principles:

- **107% Rule Filter**: Laps slower than `1.07 × field_best` are discarded as aborted/anomalous.
- **TrackStatus == '1'**: Only green-flag, clean-air laps are considered.
- **Pit lap exclusion**: `PitOutTime` and `PitInTime` are required to be `NaN`.
- **Defensive short-circuit**: If a session has no valid data (e.g., Qualifying called for degradation functions), the function returns `NaN` columns instead of crashing.
- **Universal prefix naming**: Every output column is prefixed with the session type (e.g., `fp2_`, `fp3_`, `sq_`) for unambiguous merging.

---

### 🟢 Circuit Baseline Features

#### `get_best_lap_delta(year, gp, session_type)`
Calculates the relative gap of each driver's best lap to the session's fastest lap.

| Column | Description |
|---|---|
| `{prefix}_driver_best_laptime_s` | Driver's best lap in seconds |
| `{prefix}_field_best_laptime_s` | Session fastest lap in seconds |
| `{prefix}_best_lap_delta` | `(driver_best - field_best) / field_best` — normalized relative gap |

**Formula**: `(driver_best - field_best) / field_best`

---

#### `get_clean_laps_count(year, gp, session_type)`
Counts the number of clean, representative laps per driver (within 107% threshold).

| Column | Description |
|---|---|
| `{prefix}_clean_laps_count` | Integer count of valid laps |

Drivers with zero clean laps are preserved in the output (filled with `0`).

---

#### `get_compound_avg(year, gp, session_type, compound)`
Average lap time on a specific tyre compound, corrected for degradation. Requires **at least 3 valid laps** per driver.

**Degradation correction constants**:
- SOFT: `0.12 s/lap`
- MEDIUM: `0.08 s/lap`
- HARD: `0.05 s/lap`

| Column | Description |
|---|---|
| `{prefix}_compound_{comp}_avg` | Degradation-corrected average lap time (s) |
| `{prefix}_compound_{comp}_laps` | Number of valid laps used |
| `{prefix}_compound_{comp}_best` | Absolute fastest raw lap time (s) |

---

#### `get_sector_deltas(year, gp, session_type)`
Calculates S1/S2/S3 deltas for all drivers in a single session load (efficient).

**Formula per sector**: `driver_avg_sector_time - session_best_sector_time`

| Column | Description |
|---|---|
| `{prefix}_sector1_delta` | S1 delta to field best (s) |
| `{prefix}_sector2_delta` | S2 delta to field best (s) |
| `{prefix}_sector3_delta` | S3 delta to field best (s) |

---

#### `get_max_speed_trap(year, gp, session_type)`
Extracts the maximum speed trap (`SpeedST`) value recorded per driver on valid laps.

| Column | Description |
|---|---|
| `{prefix}_max_speed_trap` | Peak speed trap reading (km/h) |
| `{prefix}_speed_trap_avg` | Average speed trap across valid laps (km/h) |
| `{prefix}_valid_laps_count` | Number of valid laps contributing |
| `{prefix}_speed_trap_delta` | Gap to the fastest driver's max speed (km/h) |

---

#### `get_laps_on_compound(year, gp, session_type, compound)`
Total laps completed by each driver on a specific tyre compound.

| Column | Description |
|---|---|
| `{prefix}_laps_on_{comp}` | Integer count of laps on compound |

---

### 🔵 Long Run / Race Simulation Features

#### `get_longrun_avg_pace(year, gp, session_type, compound, window_size=8)`
Finds the best **N strictly consecutive laps** within each driver's stint and returns their average. Requires lap numbers to be truly consecutive (no gaps from safety cars or slow laps).

**Key mechanic**: Rolling window average over `LapTime_corrected` (degradation-detrended), validated with `rolling_lap_max - rolling_lap_min == window_size - 1`.

| Column | Description |
|---|---|
| `{prefix}_longrun_{comp}_avg_pace` | Best rolling N-lap average corrected pace (s) |

---

#### `get_longrun_deg_rate(year, gp, session_type, compound, min_laps=5)`
Linear regression slope of lap times vs. tyre age. Requires ≥ `min_laps` laps per stint.

**Formula**: `np.polyfit(TyreLife, LapTime_s, deg=1)` → returns `[slope, intercept]`

| Column | Description |
|---|---|
| `{prefix}_longrun_{comp}_deg_rate` | Slope in seconds per lap (s/lap) |

Positive slope = tyres degrading. Negative slope = fuel effect outpaces wear.

---

#### `get_longrun_deg_total(year, gp, session_type, compound, min_laps=5, expected_stint_length=15)`
Extrapolates the degradation rate over a projected full stint length.

**Formula**: `deg_rate × expected_stint_length`

| Column | Description |
|---|---|
| `{prefix}_longrun_{comp}_deg_rate` | Raw slope (s/lap) |
| `{prefix}_longrun_{comp}_deg_total` | Projected total time loss over full stint (s) |

---

#### `get_longrun_consistency(year, gp, session_type, compound, min_laps=5)`
Standard deviation of degradation-corrected lap times within the primary long run stint.

- Lower = highly consistent (metronome).
- Higher = erratic (mistakes, traffic, ERS clipping).

| Column | Description |
|---|---|
| `{prefix}_longrun_{comp}_consistency` | Std dev of corrected lap times (s) |

---

#### `get_longrun_compound(year, gp, session_type, min_laps=5)`
Identifies the tyre compound used in each driver's primary long run (the longest valid stint ≥ `min_laps`).

| Column | Description |
|---|---|
| `{prefix}_longrun_compound` | Categorical: `SOFT`, `MEDIUM`, `HARD` |
| `{prefix}_longrun_stint_laps` | Number of laps in the identified stint |

---

#### `get_fuel_corrected_pace(year, gp, session_type, compound, window_size=5)`
Calculates "True Base Pace" by removing **both** tyre degradation and estimated fuel load from lap times. Allows fair comparison between drivers running different fuel programs.

**Physics constants used**:
- Fuel consumption: `1.5 kg/lap`
- Fuel safety margin: `5.0 kg`
- Fuel time penalty: `0.03 s/kg` (~0.3s per 10kg)

**Formula per lap**: `LapTime_s - (TyreLife × deg_correction) - (current_fuel_kg × 0.03)`

| Column | Description |
|---|---|
| `{prefix}_{comp}_fuel_corrected_pace` | Best rolling 5-lap 0kg-equivalent pace (s) |
| `{prefix}_{comp}_est_start_fuel_kg` | Estimated fuel load at stint start (kg) |

---

### 🟣 Power Unit / ERS Features (2026-specific)

#### `get_ers_efficiency_proxy(year, gp, session_type)`
Analyzes micro-telemetry of the fastest lap to estimate ERS efficiency. Requires `telemetry=True`.

**Definition**:
- **Recovery time**: Seconds with `Brake > 0`
- **Deployment time**: Seconds with `Throttle >= 95%`
- **Raw ratio**: `full_throttle_time / braking_time`
- **Proxy**: `raw_ratio - field_median_ratio`

| Column | Description |
|---|---|
| `braking_time_s` | Total braking time on best lap (s) |
| `full_throttle_time_s` | Total WOT time on best lap (s) |
| `{prefix}_ers_efficiency_proxy` | Delta vs field median ratio |

Positive = efficient (more deploying than recovering relative to field). Negative = clipping or inefficient recovery.

---

#### `get_lift_and_coast_laps(year, gp, session_type, min_laps=5)` *(2026-only)*
Measures average time per lap spent doing **Lift & Coast** during the primary long run. Requires `telemetry=True`.

**Universal L&C Definition**: `Speed > 250 km/h AND Throttle < 20% AND Brake == 0`

| Column | Description |
|---|---|
| `{prefix}_avg_lift_coast_time_s` | Average L&C time per lap during long run (s) |

High values indicate: battery starvation, fuel saving, or PU thermal management.

---

#### `get_pu_deployment_asymmetry(year, gp, session_type)` *(2026-only)*
Calculates the ratio between S1 and S3 times on the fastest lap as a proxy for PU deployment strategy.

**Formula**:
- `ratio = S1_time / S3_time`
- `asymmetry_delta = ratio - field_median_ratio`

| Column | Description |
|---|---|
| `{prefix}_best_s1_s` | S1 time on fastest lap (s) |
| `{prefix}_best_s3_s` | S3 time on fastest lap (s) |
| `{prefix}_s1_vs_s3_ratio` | Raw S1/S3 ratio |
| `{prefix}_pu_asymmetry_delta` | Delta vs field median strategy |

Positive delta = saving battery for S3. Negative = deploying aggressively in S1 (S3 clipping risk).

---

#### `get_speed_trap_variance(year, gp, session_type, min_laps=5)` *(2026-only)*
Standard deviation of maximum speed reached per lap during the primary long run. Requires `telemetry=True`.

| Column | Description |
|---|---|
| `{prefix}_speed_trap_std_kmh` | Std dev of max speed across long run laps (km/h) |
| `{prefix}_speed_trap_mean_kmh` | Mean max speed (km/h) |

Low variance = perfectly tuned ERS map. High variance = ERS clipping or traffic.

---

### 🟡 FP3 / Setup Tuning Features

#### `get_qualy_sim_delta(year, gp, session_type, compound)`
Delta from each driver's best push lap on the specified compound to the overall session fastest.

| Column | Description |
|---|---|
| `{prefix}_{comp}_best_lap_s` | Driver's fastest lap on compound (s) |
| `{prefix}_{comp}_best_lap_delta` | Delta to session leader (s) |

---

#### `get_fp3_vs_fp2_improvement(year, gp, compound)`
Overnight setup improvement: `FP2_best - FP3_best`.

| Column | Description |
|---|---|
| `fp2_{comp}_best_s` | FP2 best lap (s) |
| `fp3_{comp}_best_s` | FP3 best lap (s) |
| `fp3_vs_fp2_{comp}_improvement` | Time gained overnight (s, positive = faster) |

---

#### `get_sector_improvement_vs_fp2(year, gp, compound)`
Sector-by-sector overnight improvement from FP2 to FP3.

| Column | Description |
|---|---|
| `fp3_s1_delta_vs_fp2` | S1 time gained (s) |
| `fp3_s2_delta_vs_fp2` | S2 time gained (s) |
| `fp3_s3_delta_vs_fp2` | S3 time gained (s) |

Reveals aero trade-offs (e.g., drag reduction improves S1/S3 but hurts S2).

---

#### `get_fp3_qualy_sim_context(year, gp, session_type)`
Extracts the tyre compound, age, and a "True Qualy Sim" flag for the fastest lap.

**True Qualy Sim rule**: `Compound == SOFT AND TyreLife <= 3`

| Column | Description |
|---|---|
| `{prefix}_best_lap_compound` | Compound on fastest lap |
| `{prefix}_best_lap_tyre_age` | Tyre age in laps at fastest lap |
| `{prefix}_is_true_qualy_sim` | Binary: 1 = genuine qualy sim |

---

#### `get_track_evolution(year, gp, session_type)`
Global track rubbering-in metric. Splits session in two halves and compares fastest times.

**Formula**: `best_early_lap_s - best_late_lap_s` (positive = track got faster)

| Column | Description |
|---|---|
| `{prefix}_track_evolution_s` | Session-global time improvement (s), broadcast to all drivers |

---

### 🔴 Qualifying Features

#### `get_qualy_deltas(year, gp)`
Official timing data from Q1/Q2/Q3 results.

| Column | Description |
|---|---|
| `q3_time_s` | Q3 lap time in seconds (NaN if not reached) |
| `q3_delta_to_pole` | Gap to pole in Q3 (s) |
| `best_q_time_s` | Best time across Q1/Q2/Q3 (s) |
| `best_q_delta_to_pole` | Gap to pole using best available lap (s) |
| `reached_session` | Context label: `Q1`, `Q2`, `Q3`, or `DNQ` |

---

#### `get_q3_participation_flag(year, gp)`
Binary: did the driver reach Q3?

| Column | Description |
|---|---|
| `q3_participation` | `1` = reached Q3, `0` = eliminated in Q1/Q2 |

---

#### `get_qualy_vs_fp3_improvement(year, gp)`
Time gained from FP3 to Qualifying. Large positive = sandbagging.

| Column | Description |
|---|---|
| `fp3_best_s` | FP3 best lap (s) |
| `best_q_time_s` | Qualy best lap (s) |
| `q3_vs_fp3_improvement` | FP3 - Q3 time (s) |
| `best_q_vs_fp3_improvement` | FP3 - best Q time (s) |

---

#### `get_best_quali_relative_sector(year, gp)`
Identifies each driver's strongest sector relative to the field in qualifying.

| Column | Description |
|---|---|
| `quali_best_relative_sector` | Categorical: `S1`, `S2`, `S3`, or `NONE` |
| `s1_delta` | S1 gap to session fastest S1 (s) |
| `s2_delta` | S2 gap to session fastest S2 (s) |
| `s3_delta` | S3 gap to session fastest S3 (s) |

---

### ⚫ Grid & Sprint Features

#### `get_grid_position_features(year, gp, session_type='R')`
Final starting grid after all penalties from the Race session results.

| Column | Description |
|---|---|
| `grid_position` | Final grid position (pit lane starters → 21) |
| `is_front_row` | Binary: started P1 or P2 |
| `started_top_10` | Binary: started in points positions |
| `started_from_pitlane` | Binary: pit lane start |

---

#### Sprint features (SQ + S sessions)
Used for historical Miami 2024/2025 (sprint weekends).

| Column | Description |
|---|---|
| `sq_best_lap_delta` | SQ best lap delta to field leader |
| `sq_sector{1,2,3}_delta` | SQ sector deltas |
| `sq_speed_trap_delta` | SQ speed trap gap |
| `s_finish_position` | Sprint race finishing position |
| `s_grid_position` | Sprint race starting position |
| `s_positions_gained` | `grid - finish` in Sprint Race |
| `s_classified` | Binary: finished classified |

---

## 🤖 Miami 2026 Model — `miami/miami_model.py`

### Architecture

**Model**: `XGBRanker` with `rank:pairwise` objective.

The model treats each race as a **ranking group** and learns pairwise driver preferences, which is mathematically more appropriate than regression for position prediction.

### Training Data

| Race | Year | Weight | Rationale |
|---|---|---|---|
| Australia | 2026 | 1.00 | Same regulations, current-season data |
| China | 2026 | 1.00 | Same regulations, current-season data |
| Japan | 2026 | 1.00 | Same regulations, current-season data |
| Miami | 2025 | 0.22 | Same circuit, pre-2026 regs — temporal decay λ=1.5 |
| Miami | 2024 | 0.05 | Same circuit, older regs — very weak prior |

> **Temporal decay formula**: `weight = exp(-λ × Δyears)` with λ=1.5.
> 2023/2022 Miami omitted (weight < 0.01 — adds noise, no signal).

### Target Label
```
label = 22 - finish_position   (higher = better)
P1  → 21
P10 → 12
DNF → 0   (both mechanical and crash DNFs penalized equally)
```

### XGBRanker Hyperparameters

| Parameter | Value | Rationale |
|---|---|---|
| `n_estimators` | 400 | Sufficient trees for a small dataset |
| `learning_rate` | 0.02 | Low LR for better generalization |
| `max_depth` | 3 | Prevents overfitting with few samples |
| `subsample` | 0.8 | Row bagging |
| `colsample_bytree` | 0.7 | Column bagging |
| `min_child_weight` | 2 | Regularizes leaf splits |
| `reg_alpha` | 2.0 | L1 sparsity |
| `reg_lambda` | 4.0 | L2 weight shrinkage |
| `gamma` | 0.1 | Minimum gain for split |

### Feature Columns Used

#### FP1 (all weekends)
```
fp1_best_lap_delta, fp1_clean_laps_count,
fp1_sector{1,2,3}_delta, fp1_max_speed_trap,
fp1_speed_trap_delta, fp1_compound_medium_avg, fp1_laps_on_hard
```

#### FP2 — Race Simulation (standard weekends)
```
fp2_best_lap_delta, fp2_clean_laps_count,
fp2_sector{1,2,3}_delta, fp2_max_speed_trap,
fp2_longrun_medium_avg_pace, fp2_longrun_medium_deg_rate,
fp2_longrun_medium_deg_total, fp2_longrun_medium_consistency,
fp2_longrun_hard_avg_pace, fp2_longrun_hard_deg_rate,
fp2_medium_fuel_corrected_pace,
fp2_pu_asymmetry_delta,       ← 2026-only (NaN for historical)
fp2_speed_trap_std_kmh,       ← 2026-only (NaN for historical)
fp2_avg_lift_coast_time_s,    ← 2026-only (NaN for historical)
fp2_ers_efficiency_proxy      ← 2026-only (NaN for historical)
```

#### FP3 — Final Tune (standard weekends)
```
fp3_best_lap_delta, fp3_sector{1,2,3}_delta,
fp3_soft_best_lap_delta, fp3_vs_fp2_soft_improvement,
fp3_s{1,2,3}_delta_vs_fp2, fp3_is_true_qualy_sim,
fp3_track_evolution_s
```

#### Sprint (sprint weekends — NaN for standard)
```
sq_best_lap_delta, sq_sector{1,2,3}_delta,
sq_speed_trap_delta, s_finish_position,
s_positions_gained, s_classified
```

#### Qualifying (always available)
```
grid_position, is_front_row, started_top_10,
q3_delta_to_pole, best_q_delta_to_pole,
q3_participation, best_q_vs_fp3_improvement,
quali_best_relative_sector
```

#### Team / Power Unit
```
pu_score, is_works, pu_is_works
```

#### 2026-Specific Engineered Features
```
has_upgrade_this_weekend, dnf_rate_2026,
ers_clipping_penalty_index
```

### Power Unit Scoring (2026 Regulations)

| Constructor | PU Score | Is Works |
|---|---|---|
| Mercedes | 5 | ✅ |
| McLaren | 5 | ❌ (customer) |
| Williams | 5 | ❌ |
| Alpine | 5 | ❌ |
| Haas | 4 | ❌ |
| Ferrari | 3.5 | ✅ |
| Red Bull Racing | 3 | ✅ |
| Racing Bulls | 3 | ❌ |
| Audi | 2 | ✅ |
| Cadillac | 2 | ❌ |
| Aston Martin | 1 | ✅ |

**Interaction term**: `pu_is_works = pu_score × is_works`
This separates Mercedes (5×1=5) from McLaren-Mercedes customer (5×0=0).

### Derived Feature: ERS Clipping Penalty Index
```python
ers_clipping_penalty_index = |pu_asymmetry_delta| × |ers_efficiency_proxy|
                              (only when both are negative)
```
Captures the combined risk of S3 battery starvation AND inefficient ERS usage.

### Miami Circuit Profile
```python
MIAMI_CIRCUIT_PROFILE = {
    "high_speed_ratio":     0.55,   # % of lap at high speed
    "overtaking_difficulty": 0.45,  # 0=easy, 1=Monaco
    "brake_intensity":       0.65,  # ERS harvest potential
    "pu_sensitivity":        0.70,  # PU vs aero importance
    "street_circuit":        0,     # permanent circuit
    "traction_zones":        0.60,  # slow-corner traction
}
```

### Preprocessing Pipeline

1. Categorical columns (e.g., `quali_best_relative_sector`) → `pd.get_dummies(drop_first=True)`
2. All columns cast to `float` — non-numeric values → `NaN`
3. Sprint/FP2/FP3 mismatch → `NaN` columns (XGBoost Sparsity-Aware Split handles natively)
4. Inference: output aligned to training schema (missing columns → `0.0`)

### Weekend Type Detection
```python
is_sprint = event.get_session_name(4) == "Sprint"
```
- Sprint weekend → SQ+S features (FP2/FP3 columns = NaN)
- Standard weekend → FP2+FP3 features (SQ/S columns = NaN)

---

## 📊 Pipeline Execution Flow

```
Phase 1: Build Training Set
  ├── Australia 2026 → extract_fp1 + extract_fp2 + extract_fp3 + extract_quali + team
  ├── China 2026     → extract_fp1 + extract_fp2 + extract_fp3 + extract_quali + team
  ├── Japan 2026     → extract_fp1 + extract_fp2 + extract_fp3 + extract_quali + team
  ├── Miami 2025     → extract_fp1 + extract_sprint (SQ+S) + extract_quali + team
  └── Miami 2024     → extract_fp1 + extract_sprint (SQ+S) + extract_quali + team

Phase 2: Build Miami 2026 Feature Matrix (inference, no labels)
  └── extract_fp1 + extract_fp2 + extract_fp3 + extract_quali + team + circuit_context

Phase 3: Train XGBRanker
  └── Groups = [n_drivers_race_1, ..., n_drivers_race_5]
      Weights = [1.0, 1.0, 1.0, 0.22, 0.05]

Phase 4: Predict Miami 2026
  └── rank_score per driver → sort descending → predicted_position
```

---

## 🛠️ Dependencies

```toml
[dependencies]
fastf1 = ">=3.4"
pandas = ">=2.0"
numpy = ">=1.26"
xgboost = ">=2.0"
```

---

## 🚀 Usage

```bash
# From the project root
cd miami
python miami_model.py
```

FastF1 cache is populated automatically on first run. Subsequent runs are significantly faster.

---

## 📝 Notes on 2026 ERS Features

The 2026 regulations introduced a radically different hybrid system with **higher electrical power deployment**. Three new features were added specifically for 2026:

1. **`fp2_avg_lift_coast_time_s`** — measures battery starvation (L&C events at racing speed)
2. **`fp2_ers_efficiency_proxy`** — measures deploy/recover balance on the fastest lap
3. **`fp2_speed_trap_std_kmh`** — measures ERS consistency across long run laps

These features will be `NaN` for all pre-2026 historical rows. XGBoost handles this natively via its Sparsity-Aware Split Finding algorithm — it learns separate split directions for missing values and effectively treats historical rows as having "no 2026 ERS signal."
