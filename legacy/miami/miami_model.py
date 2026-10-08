import os, sys, importlib, json, warnings
import numpy as np
import pandas as pd
from xgboost import XGBRanker

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# 0. DYNAMIC IMPORT OF FEATURE ENGINEERING MODULE
# ─────────────────────────────────────────────────────────────────────────────
_spec = importlib.util.spec_from_file_location(
    "f1_fe",
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "f1-api", "f1_fe.py")
    ),
)
f1_fe = importlib.util.module_from_spec(_spec)
sys.modules["f1_fe"] = f1_fe
_spec.loader.exec_module(f1_fe)

import fastf1

fastf1.Cache.enable_cache("./.f1_cache")

# ─────────────────────────────────────────────────────────────────────────────
# 1. CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

with open("team_mappings.json", "r") as f:
    MAPS = json.load(f)

PU_MAP = MAPS["PU_MAP"]
WORKS_MAP = MAPS["WORKS_MAP"]

# 2026 races with known results → training set
TRAINING_RACES_2026 = [
    {"year": 2026, "gp": "Australia", "weight": 1.0},
    {"year": 2026, "gp": "China", "weight": 1.0},
    {"year": 2026, "gp": "Japan", "weight": 1.0},
]

# Historical Miami races — same circuit, different regulations
# Pre-2026 data used as weak prior with exponential temporal decay
# λ=1.5 → 2025≈0.22, 2024≈0.05. Anything before 2024 is noise.
HISTORICAL_MIAMI = [
    {"year": 2025, "gp": "Miami", "weight": 0.22},
    {"year": 2024, "gp": "Miami", "weight": 0.05},
    # 2023/2022 omitted — weight < 0.01, adds noise more than signal
]

TARGET_RACE = {"year": 2026, "gp": "Miami"}

# Circuit profile for Miami — used to contextualize PU sensitivity
MIAMI_CIRCUIT_PROFILE = {
    "high_speed_ratio": 0.55,  # % of lap at high speed (lower than Suzuka)
    "overtaking_difficulty": 0.45,  # 0=easy, 1=Monaco
    "brake_intensity": 0.65,  # proxy for ERS harvest potential
    "pu_sensitivity": 0.70,  # how much PU vs aero determines lap time
    "street_circuit": 0,  # permanent circuit
    "traction_zones": 0.60,  # slow-speed traction sensitivity
}

FEATURE_COLS = [
        # ── FP1 (all weekends) ────────────────────────────────────────────────
        "fp1_best_lap_delta",
        "fp1_clean_laps_count",
        "fp1_sector1_delta",
        "fp1_sector2_delta",
        "fp1_sector3_delta",
        "fp1_max_speed_trap",
        "fp1_speed_trap_delta",
        "fp1_compound_medium_avg",
        "fp1_laps_on_hard",
        # ── FP2 long run (standard weekends → NaN in sprint races) ───────────
        "fp2_best_lap_delta",
        "fp2_clean_laps_count",
        "fp2_sector1_delta",
        "fp2_sector2_delta",
        "fp2_sector3_delta",
        "fp2_max_speed_trap",
        "fp2_longrun_medium_avg_pace",
        "fp2_longrun_medium_deg_rate",
        "fp2_longrun_medium_deg_total",
        "fp2_longrun_medium_consistency",
        "fp2_longrun_hard_avg_pace",
        "fp2_longrun_hard_deg_rate",
        "fp2_medium_fuel_corrected_pace",
        "fp2_pu_asymmetry_delta",  # 2026-only: NaN for historical
        "fp2_speed_trap_std_kmh",  # 2026-only: ERS variance
        "fp2_avg_lift_coast_time_s",  # 2026-only: battery starvation proxy
        "fp2_ers_efficiency_proxy",  # 2026-only: deploy vs recover ratio
        # ── FP3 (standard weekends → NaN in sprint races) ─────────────────────
        "fp3_best_lap_delta",
        "fp3_sector1_delta",
        "fp3_sector2_delta",
        "fp3_sector3_delta",
        "fp3_soft_best_lap_delta",
        "fp3_vs_fp2_soft_improvement",
        "fp3_s1_delta_vs_fp2",
        "fp3_s2_delta_vs_fp2",
        "fp3_s3_delta_vs_fp2",
        "fp3_is_true_qualy_sim",
        "fp3_track_evolution_s",
        # ── Sprint sessions (sprint weekends → NaN for standard) ──────────────
        "sq_best_lap_delta",
        "sq_sector1_delta",
        "sq_sector2_delta",
        "sq_sector3_delta",
        "sq_speed_trap_delta",
        "s_finish_position",
        "s_positions_gained",
        "s_classified",
        # ── Qualifying (always available) ─────────────────────────────────────
        "grid_position",
        "is_front_row",
        "started_top_10",
        "q3_delta_to_pole",
        "best_q_delta_to_pole",
        "q3_participation",
        "best_q_vs_fp3_improvement",
        "quali_best_relative_sector",  # categorical → one-hot encoded
        # ── Team / Power Unit (strongest structural feature in 2026) ──────────
        "pu_score",
        "is_works",
        "pu_is_works",  # interaction: works advantage × PU level
        # ── New 2026 specific features ─────────────────────────────────────────
        "has_upgrade_this_weekend",
        "dnf_rate_2026",
        "ers_clipping_penalty_index",
    ]


# ─────────────────────────────────────────────────────────────────────────────
# 2. FEATURE EXTRACTION HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def safe_merge(
    base: pd.DataFrame, df: pd.DataFrame, on: str = "Driver"
) -> pd.DataFrame:
    """Defensive merge — if df is empty or None, returns base unchanged."""
    if df is None or df.empty:
        return base
    cols = [c for c in df.columns if c not in base.columns or c == on]
    return base.merge(df[cols], on=on, how="left")


def get_base_drivers(year: int, gp: str) -> pd.DataFrame:
    """
    Loads the driver list from Qualifying results.
    Falls back to Race results if Qualifying data is unavailable.
    """
    for session_type in ["Q", "SQ", "R", "S"]:
        try:
            s = fastf1.get_session(year, gp, session_type)
            s.load(telemetry=False, weather=False, messages=False)
            drivers = s.results["Abbreviation"].tolist()
            if drivers:
                return pd.DataFrame({"Driver": drivers, "year": year, "gp": gp})
        except Exception:
            continue
    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# 3. SESSION FEATURE EXTRACTORS
# ─────────────────────────────────────────────────────────────────────────────


def extract_fp1_features(year: int, gp: str) -> pd.DataFrame:
    """
    FP1 — Circuit baseline.
    Available in all weekend formats.
    Lower weight in model: teams running setup programs, not full pace.
    """
    print(f"    [FP1] Extracting features for {gp} {year}")
    dfs = []

    for fn, kwargs, label in [
        (f1_fe.get_best_lap_delta, {"session_type": "FP1"}, "best_lap_delta"),
        (f1_fe.get_clean_laps_count, {"session_type": "FP1"}, "clean_laps_count"),
        (f1_fe.get_sector_deltas, {"session_type": "FP1"}, "sector_deltas"),
        (f1_fe.get_max_speed_trap, {"session_type": "FP1"}, "speed_trap"),
        (
            f1_fe.get_compound_avg,
            {"session_type": "FP1", "compound": "MEDIUM"},
            "compound_medium",
        ),
        (
            f1_fe.get_laps_on_compound,
            {"session_type": "FP1", "compound": "HARD"},
            "laps_on_hard",
        ),
    ]:
        try:
            dfs.append(fn(year, gp, **kwargs))
        except Exception as e:
            print(f"      WARN fp1.{label}: {e}")

    if not dfs:
        return pd.DataFrame()
    result = dfs[0]
    for df in dfs[1:]:
        result = safe_merge(result, df)
    return result


def extract_fp2_features(year: int, gp: str) -> pd.DataFrame:
    """
    FP2 — Race simulation. Highest-weight session in the model.
    Long runs reveal true race pace, degradation, and ERS management.
    Only available in standard weekends (not sprints).

    2026 note: fp2_lift_coast and ERS asymmetry are new 2026-specific
    features not present in historical data → will be NaN for pre-2026 rows.
    The imputer handles this gracefully.
    """
    print(f"    [FP2] Extracting features for {gp} {year}")
    dfs = []

    # ── Basic pace ────────────────────────────────────────────────────────────
    for fn, kwargs, label in [
        (f1_fe.get_best_lap_delta, {"session_type": "FP2"}, "best_lap_delta"),
        (f1_fe.get_clean_laps_count, {"session_type": "FP2"}, "clean_laps_count"),
        (f1_fe.get_sector_deltas, {"session_type": "FP2"}, "sector_deltas"),
        (f1_fe.get_max_speed_trap, {"session_type": "FP2"}, "speed_trap"),
    ]:
        try:
            dfs.append(fn(year, gp, **kwargs))
        except Exception as e:
            print(f"      WARN fp2.{label}: {e}")

    # ── Long run — the core of the model ─────────────────────────────────────
    for compound in ["MEDIUM", "HARD"]:
        for fn, label in [
            (f1_fe.get_longrun_avg_pace, "longrun_avg_pace"),
            (f1_fe.get_longrun_deg_rate, "longrun_deg_rate"),
            (f1_fe.get_longrun_deg_total, "longrun_deg_total"),
            (f1_fe.get_longrun_consistency, "longrun_consistency"),
        ]:
            try:
                dfs.append(fn(year, gp, "FP2", compound=compound))
            except Exception as e:
                print(f"      WARN fp2.{label} [{compound}]: {e}")

    # ── Advanced features (fuel correction + ERS) ─────────────────────────────
    for fn, kwargs, label in [
        (
            f1_fe.get_fuel_corrected_pace,
            {"session_type": "FP2", "compound": "MEDIUM"},
            "fuel_corrected",
        ),
        (f1_fe.get_pu_deployment_asymmetry, {"session_type": "FP2"}, "pu_asymmetry"),
        (f1_fe.get_speed_trap_variance, {"session_type": "FP2"}, "speed_variance"),
    ]:
        try:
            dfs.append(fn(year, gp, **kwargs))
        except Exception as e:
            print(f"      WARN fp2.{label}: {e}")

    # ── 2026-specific ERS metrics ─────────────────────────────────────────────
    # Only meaningful for 2026 data — NaN for historical rows (expected)
    for fn, kwargs, label in [
        (f1_fe.get_lift_and_coast_laps, {"session_type": "FP2"}, "lift_coast"),
        (f1_fe.get_ers_efficiency_proxy, {"session_type": "FP2"}, "ers_efficiency"),
    ]:
        try:
            dfs.append(fn(year, gp, **kwargs))
        except Exception as e:
            print(
                f"      WARN fp2.{label} (2026-only, NaN expected for historical): {e}"
            )

    if not dfs:
        return pd.DataFrame()
    result = dfs[0]
    for df in dfs[1:]:
        result = safe_merge(result, df)
    return result


def extract_fp3_features(year: int, gp: str) -> pd.DataFrame:
    """
    FP3 — Final setup tuning + qualifying simulation.
    The overnight delta vs FP2 reveals how much pace teams found.
    Only available in standard weekends.
    """
    print(f"    [FP3] Extracting features for {gp} {year}")
    dfs = []

    for fn, kwargs, label in [
        (f1_fe.get_best_lap_delta, {"session_type": "FP3"}, "best_lap_delta"),
        (f1_fe.get_clean_laps_count, {"session_type": "FP3"}, "clean_laps_count"),
        (f1_fe.get_sector_deltas, {"session_type": "FP3"}, "sector_deltas"),
        (f1_fe.get_max_speed_trap, {"session_type": "FP3"}, "speed_trap"),
        (
            f1_fe.get_qualy_sim_delta,
            {"session_type": "FP3", "compound": "SOFT"},
            "qualy_sim",
        ),
        (f1_fe.get_fp3_vs_fp2_improvement, {}, "fp3_vs_fp2"),
        (f1_fe.get_sector_improvement_vs_fp2, {}, "sector_improvement"),
        (f1_fe.get_fp3_qualy_sim_context, {"session_type": "FP3"}, "qualy_sim_context"),
        (f1_fe.get_track_evolution, {"session_type": "FP3"}, "track_evolution"),
    ]:
        try:
            dfs.append(fn(year, gp, **kwargs))
        except Exception as e:
            print(f"      WARN fp3.{label}: {e}")

    if not dfs:
        return pd.DataFrame()
    result = dfs[0]
    for df in dfs[1:]:
        result = safe_merge(result, df)
    return result


def extract_sprint_features(year: int, gp: str) -> pd.DataFrame:
    """
    SQ + S — Sprint Qualifying and Sprint Race.
    Used for historical Miami 2024/2025 which were sprint weekends.
    Sprint race result is the strongest real-race-pace signal available
    in a sprint weekend — treated similarly to a FP2 long run proxy.
    """
    print(f"    [SQ+S] Extracting features for {gp} {year}")
    dfs = []

    for fn, kwargs, label in [
        (f1_fe.get_best_lap_delta, {"session_type": "SQ"}, "sq_best_lap_delta"),
        (f1_fe.get_sector_deltas, {"session_type": "SQ"}, "sq_sector_deltas"),
        (f1_fe.get_max_speed_trap, {"session_type": "SQ"}, "sq_speed_trap"),
        (f1_fe.get_clean_laps_count, {"session_type": "SQ"}, "sq_clean_laps"),
    ]:
        try:
            dfs.append(fn(year, gp, **kwargs))
        except Exception as e:
            print(f"      WARN sprint.{label}: {e}")

    # Sprint race result — real competitive order under race conditions
    try:
        session_s = fastf1.get_session(year, gp, "S")
        session_s.load(telemetry=False, weather=False, messages=False)
        res = session_s.results
        df_sprint = pd.DataFrame(
            {
                "Driver": res["Abbreviation"],
                "s_finish_position": pd.to_numeric(res["Position"], errors="coerce"),
                "s_grid_position": pd.to_numeric(res["GridPosition"], errors="coerce"),
                "s_positions_gained": (
                    pd.to_numeric(res["GridPosition"], errors="coerce")
                    - pd.to_numeric(res["Position"], errors="coerce")
                ),
                "s_classified": (
                    res["Status"].str.contains("Finished|Lap", na=False)
                ).astype(int),
            }
        )
        dfs.append(df_sprint)
    except Exception as e:
        print(f"      WARN sprint.race_results: {e}")

    if not dfs:
        return pd.DataFrame()
    result = dfs[0]
    for df in dfs[1:]:
        result = safe_merge(result, df)
    return result


def extract_quali_features(year: int, gp: str) -> pd.DataFrame:
    """
    Q — Main qualifying session.
    Strongest individual predictor (grid position alone explains ~60% of variance).
    """
    print(f"    [Q] Extracting features for {gp} {year}")
    dfs = []

    for fn, kwargs, label in [
        (f1_fe.get_qualy_deltas, {}, "qualy_deltas"),
        (f1_fe.get_q3_participation_flag, {}, "q3_flag"),
        (f1_fe.get_qualy_vs_fp3_improvement, {}, "qualy_vs_fp3"),
        (f1_fe.get_best_quali_relative_sector, {}, "best_sector"),
        (f1_fe.get_grid_position_features, {"session_type": "R"}, "grid_features"),
    ]:
        try:
            dfs.append(fn(year, gp, **kwargs))
        except Exception as e:
            print(f"      WARN quali.{label}: {e}")

    if not dfs:
        return pd.DataFrame()
    result = dfs[0]
    for df in dfs[1:]:
        result = safe_merge(result, df)
    return result


def extract_team_features(year: int, gp: str) -> pd.DataFrame:
    """
    PU score and works status from 2026 maps.

    pu_is_works = pu_score × is_works creates an interaction term that
    separates Mercedes works (5×1=5) from McLaren-Mercedes (5×0=0),
    even though both share the same power unit specification.

    For pre-2026 historical data: teams are remapped to 2026 equivalents
    since the model needs to apply 2026 PU scores to all rows.
    The historical PU hierarchy was different but we still apply the 2026
    map — this is intentional, as we want the model to learn driver/team
    patterns, not learn the old PU hierarchy.
    """
    print(f"    [TEAM] Extracting features for {gp} {year}")
    try:
        df_team = f1_fe.get_team_info(year, gp, "Q")

        # Normalize team names — fastf1 uses full names, maps use short names
        TEAM_NAME_MAP = {
            "Mercedes-AMG Petronas F1 Team": "Mercedes",
            "McLaren F1 Team": "McLaren",
            "Scuderia Ferrari": "Ferrari",
            "Williams Racing": "Williams",
            "BWT Alpine F1 Team": "Alpine",
            "Aston Martin Aramco F1 Team": "Aston Martin",
            "Oracle Red Bull Racing": "Red Bull Racing",
            "Visa Cash App RB F1 Team": "Racing Bulls",
            "MoneyGram Haas F1 Team": "Haas",
            "Audi F1 Team": "Audi",
            "Cadillac F1 Team": "Cadillac",
            # Legacy names for historical data
            "Kick Sauber": "Audi",  # → became Audi in 2026
            "AlphaTauri": "Racing Bulls",
            "Alfa Romeo": "Audi",
            "Aston Martin Aramco Mercedes": "Aston Martin",
        }

        df_team["Team_norm"] = df_team["Team"].replace(TEAM_NAME_MAP)
        df_team["pu_score"] = df_team["Team_norm"].map(PU_MAP).fillna(2).astype(float)
        df_team["is_works"] = (
            df_team["Team_norm"].map(WORKS_MAP).fillna(0).astype(float)
        )
        df_team["pu_is_works"] = df_team["pu_score"] * df_team["is_works"]

        # Fix 3: Add McLaren upgrade flag
        df_team["has_upgrade_this_weekend"] = (
            df_team["Team_norm"] == "McLaren"
        ).astype(int)

        # Fix 4: Add reliability feature (DNF rate) for early 2026 season
        DNF_RATE_MAP = {
            "Audi": 0.25,
            "Racing Bulls": 0.25,
            "Alpine": 0.15,
        }
        df_team["dnf_rate_2026"] = df_team["Team_norm"].map(DNF_RATE_MAP).fillna(0.0)

        return df_team[
            [
                "Driver",
                "Team",
                "pu_score",
                "is_works",
                "pu_is_works",
                "has_upgrade_this_weekend",
                "dnf_rate_2026",
            ]
        ]
    except Exception as e:
        print(f"      WARN team_features: {e}")
        return pd.DataFrame()


def add_circuit_context(df: pd.DataFrame) -> pd.DataFrame:
    """
    Appends Miami circuit profile as constant columns.
    These act as context features — they don't vary by driver but help
    the model generalize across different circuits in future seasons.
    """
    for key, val in MIAMI_CIRCUIT_PROFILE.items():
        df[f"circuit_{key}"] = val
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 4. FULL FEATURE MATRIX BUILDER
# ─────────────────────────────────────────────────────────────────────────────


def build_race_features(
    year: int, gp: str, include_circuit_context: bool = False
) -> pd.DataFrame:
    """
    Assembles the complete feature vector per race.
    Handles sprint vs. standard weekends automatically.
    Missing session data → NaN columns (XGBoost handles downstream via Sparsity-aware Split Finding).
    """
    try:
        event = fastf1.get_event(year, gp)
        is_sprint = event.get_session_name(4) == "Sprint"
    except Exception:
        is_sprint = False
    print(f"\n  {'─' * 55}")
    print(
        f"  Building features: {gp} {year} "
        f"({'Sprint' if is_sprint else 'Standard'} weekend)"
    )
    print(f"  {'─' * 55}")

    base = get_base_drivers(year, gp)
    if base.empty:
        print(f"  ERROR: Could not load driver list for {gp} {year}")
        return pd.DataFrame()

    # FP1 — always available
    base = safe_merge(base, extract_fp1_features(year, gp))

    # Practice format depends on weekend type
    if is_sprint:
        # Sprint weekend: SQ and S replace FP2/FP3
        # FP2/FP3 columns will be NaN — imputer fills with training median
        base = safe_merge(base, extract_sprint_features(year, gp))
    else:
        # Standard weekend: FP2 (race sim) + FP3 (final tune)
        base = safe_merge(base, extract_fp2_features(year, gp))
        base = safe_merge(base, extract_fp3_features(year, gp))

    # Qualifying — always available
    base = safe_merge(base, extract_quali_features(year, gp))

    # Team / PU
    base = safe_merge(base, extract_team_features(year, gp))

    # Circuit context
    if include_circuit_context:
        base = add_circuit_context(base)

    # ── Feature Engineering No Lineal: Riesgo de Clipping ERS ───────────────
    if "fp2_ers_efficiency_proxy" in base.columns and "fp2_pu_asymmetry_delta" in base.columns:
        asymmetry_risk = np.where(base["fp2_pu_asymmetry_delta"] < 0, np.abs(base["fp2_pu_asymmetry_delta"]), 0)
        inefficiency_risk = np.where(base["fp2_ers_efficiency_proxy"] < 0, np.abs(base["fp2_ers_efficiency_proxy"]), 0)
        base["ers_clipping_penalty_index"] = asymmetry_risk * inefficiency_risk
    else:
        base["ers_clipping_penalty_index"] = np.nan

    print(f"  → {len(base)} drivers, {len(base.columns)} raw columns")
    return base


# ─────────────────────────────────────────────────────────────────────────────
# 5. RACE RESULT LABELS
# ─────────────────────────────────────────────────────────────────────────────


def get_race_labels(year: int, gp: str) -> pd.DataFrame:
    """
    Extracts finishing position as training label.
    XGBRanker with rank:pairwise requires: higher score = better result.
    Transform: label = 22 - finishing_position
      P1  → 21 (best)
      P10 → 12
      DNF → 0  (worst, penalized)
    """
    try:
        session = fastf1.get_session(year, gp, "R")
        session.load(telemetry=False, weather=False, messages=False)
        res = session.results

        df = pd.DataFrame(
            {
                "Driver": res["Abbreviation"],
                "finish_pos": pd.to_numeric(res["Position"], errors="coerce").fillna(
                    22
                ),
                "status": res["Status"],
            }
        )

        # Penalize crash DNFs equally to mechanical DNFs instead of dropping them
        # (Dropping them causes NaN labels downstream after merge)
        crash_keywords = "Accident|Collision|Spun off|Damage"
        crash_mask = df["status"].str.contains(crash_keywords, na=False, case=False)
        df.loc[crash_mask, "finish_pos"] = 22

        # Penalize mechanical DNF/DNS/DSQ — they lost competitive value due to reliability
        dnf_mask = ~df["status"].str.contains("Finished|Lap", na=False)
        df.loc[dnf_mask, "finish_pos"] = 22

        # Higher label = better result (XGBRanker convention)
        df["label"] = (22 - df["finish_pos"]).clip(lower=0).astype(int)

        return df[["Driver", "finish_pos", "label"]]
    except Exception as e:
        print(f"  ERROR loading labels for {gp} {year}: {e}")
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
# 6. FULL DATASET BUILDER
# ─────────────────────────────────────────────────────────────────────────────


def build_full_training_set(races: list[dict]) -> pd.DataFrame:
    """
    Builds and concatenates feature matrices for all training races.
    Each row = one driver in one race.
    Sample weights are attached per the temporal decay configuration.
    """
    all_dfs = []

    for race in races:
        print(f"\n{'=' * 60}")
        print(f"Processing: {race['gp']} {race['year']} (weight={race['weight']:.2f})")
        print(f"{'=' * 60}")

        features = build_race_features(race["year"], race["gp"])
        if features.empty:
            print(f"  SKIP: no feature data for {race['gp']} {race['year']}")
            continue

        labels = get_race_labels(race["year"], race["gp"])
        if labels.empty:
            print(f"  SKIP: no label data for {race['gp']} {race['year']}")
            continue

        df = features.merge(labels, on="Driver", how="left")
        df = df.dropna(
            subset=["label"]
        )  # drop drivers with no label (e.g., DNS before start)
        df["label"] = df["label"].astype(int)
        df["sample_weight"] = race["weight"]
        df["is_2026"] = int(race["year"] == 2026)

        all_dfs.append(df)

    if not all_dfs:
        raise ValueError("No races with valid data — check fastf1 cache.")

    combined = pd.concat(all_dfs, axis=0, ignore_index=True)
    print(f"\n{'=' * 60}")
    print(
        f"Training set assembled: {len(combined)} rows × "
        f"{len(combined.columns)} columns"
    )
    print(
        f"  2026 rows: {combined['is_2026'].sum()} "
        f"| Historical rows: {(~combined['is_2026'].astype(bool)).sum()}"
    )
    print(f"{'=' * 60}")
    return combined


# ─────────────────────────────────────────────────────────────────────────────
# 7. PREPROCESSING
# ─────────────────────────────────────────────────────────────────────────────


def preprocess(
    df: pd.DataFrame,
    feature_cols: list[str],
    known_cols: list[str] = None,
) -> tuple[pd.DataFrame, list[str]]:
    """
    known_cols: if provided (inference mode), aligns output to training schema.
    """
    cat_cols = [c for c in feature_cols if c in df.columns and df[c].dtype == object]

    for col in feature_cols:
        if col not in df.columns:
            df[col] = np.nan

    df_enc = pd.get_dummies(df[feature_cols], columns=cat_cols, drop_first=True)
    df_enc = df_enc.apply(pd.to_numeric, errors="coerce")
    df_enc = df_enc.select_dtypes(include=[np.number])

    if known_cols is not None:
        # Inference: align to training schema
        for col in known_cols:
            if col not in df_enc.columns:
                df_enc[col] = 0.0
        df_enc = df_enc[known_cols]

    final_cols = df_enc.columns.tolist()
    X = df_enc.to_numpy(dtype=float)

    print(f"    [preprocess] shape: {X.shape}, cols: {len(final_cols)}")
    return pd.DataFrame(X, columns=final_cols), final_cols


# ─────────────────────────────────────────────────────────────────────────────
# 8. MODEL TRAINING
# ─────────────────────────────────────────────────────────────────────────────


def train_model(df_train: pd.DataFrame, feature_cols: list[str]):

    df_train = df_train.sort_values(["year", "gp"]).reset_index(drop=True)

    X_raw = df_train[feature_cols]
    y = df_train["label"].values.astype(int)

    X_proc, final_cols = preprocess(X_raw, feature_cols)

    race_order = df_train[["year", "gp"]].drop_duplicates()
    groups = []
    group_weights = []

    for _, row in race_order.iterrows():
        mask = (df_train["year"] == row["year"]) & (df_train["gp"] == row["gp"])
        groups.append(mask.sum())
        group_weights.append(df_train.loc[mask, "sample_weight"].iloc[0])

    print(f"\n  Training groups (drivers per race): {groups}")
    print(
        f"  Group weights:                      {[round(w, 2) for w in group_weights]}"
    )
    print(f"  Total samples: {sum(groups)}")
    print(f"  Features after encoding: {len(final_cols)}")

    model = XGBRanker(
        objective="rank:pairwise",
        n_estimators=400,
        learning_rate=0.02,
        max_depth=3,
        subsample=0.8,
        colsample_bytree=0.7,
        min_child_weight=2,
        reg_alpha=2.0,
        reg_lambda=4.0,
        gamma=0.1,
        random_state=42,
        verbosity=0,
    )

    model.fit(
        X_proc,
        y,
        group=groups,
        sample_weight=group_weights,  # ← 5 weights, one per race
    )

    return model, final_cols


# ─────────────────────────────────────────────────────────────────────────────
# 9. INFERENCE
# ─────────────────────────────────────────────────────────────────────────────


def predict_top(
    model,
    final_cols: list[str],
    df_target: pd.DataFrame,
    feature_cols: list[str],
) -> pd.DataFrame:

    # ── FIX: add missing columns as NaN BEFORE indexing ──────────────────────
    # df_miami may not have FP2/FP3/sprint columns if sessions weren't available
    # or if this is a different weekend format than training races.
    # preprocess() already handles this internally, but the indexing
    # df_target[feature_cols] happens before preprocess is called — so it crashes.
    df_inference = df_target.copy()
    for col in feature_cols:
        if col not in df_inference.columns:
            df_inference[col] = np.nan
    # ─────────────────────────────────────────────────────────────────────────

    X_raw = df_inference[feature_cols]  # now safe — all columns exist

    X_proc, _ = preprocess(X_raw, feature_cols, known_cols=final_cols)

    scores = model.predict(X_proc.values)

    df_result = df_target[["Driver"]].copy()
    if "Team" in df_target.columns:
        df_result["Team"] = df_target["Team"].values

    df_result["rank_score"] = scores
    df_result = df_result.sort_values("rank_score", ascending=False).reset_index(
        drop=True
    )
    df_result["predicted_position"] = df_result.index + 1

    return df_result.head(22)


# ─────────────────────────────────────────────────────────────────────────────
# 10. FEATURE IMPORTANCE REPORT
# ─────────────────────────────────────────────────────────────────────────────


def print_feature_importance(model, final_cols: list[str], top_n: int = 25):
    importance = (
        pd.DataFrame(
            {
                "feature": final_cols,
                "importance": model.feature_importances_,
            }
        )
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )

    print(f"\n{'─' * 60}")
    print(f"  TOP {top_n} FEATURE IMPORTANCES")
    print(f"{'─' * 60}")

    # Group by session prefix for a high-level summary
    importance["session"] = importance["feature"].str.split("_").str[0].str.upper()
    session_totals = (
        importance.groupby("session")["importance"].sum().sort_values(ascending=False)
    )
    print("\n  Session-level breakdown:")
    for sess, total in session_totals.items():
        bar = "█" * int(total * 30)
        print(f"    {sess:<6} {bar:<30} {total:.3f}")

    print(f"\n  Top {top_n} individual features:")
    for i, row in importance.head(top_n).iterrows():
        bar = "█" * int(row["importance"] * 300)
        print(f"    {i + 1:>2}. {row['feature']:<45} {bar} {row['importance']:.4f}")


# ─────────────────────────────────────────────────────────────────────────────
# 11. MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # ── Feature columns ───────────────────────────────────────────────────────
    # All sessions contribute features. Sprint/FP2-FP3 mismatch → native XGBoost handling.
    # 2026-only ERS features → NaN for historical rows → native XGBoost handling.
    FEATURE_COLS = [
        # ── FP1 (all weekends) ────────────────────────────────────────────────
        "fp1_best_lap_delta",
        "fp1_clean_laps_count",
        "fp1_sector1_delta",
        "fp1_sector2_delta",
        "fp1_sector3_delta",
        "fp1_max_speed_trap",
        "fp1_speed_trap_delta",
        "fp1_compound_medium_avg",
        "fp1_laps_on_hard",
        # ── FP2 long run (standard weekends → NaN in sprint races) ───────────
        "fp2_best_lap_delta",
        "fp2_clean_laps_count",
        "fp2_sector1_delta",
        "fp2_sector2_delta",
        "fp2_sector3_delta",
        "fp2_max_speed_trap",
        "fp2_longrun_medium_avg_pace",
        "fp2_longrun_medium_deg_rate",
        "fp2_longrun_medium_deg_total",
        "fp2_longrun_medium_consistency",
        "fp2_longrun_hard_avg_pace",
        "fp2_longrun_hard_deg_rate",
        "fp2_medium_fuel_corrected_pace",
        "fp2_pu_asymmetry_delta",  # 2026-only: NaN for historical
        "fp2_speed_trap_std_kmh",  # 2026-only: ERS variance
        "fp2_avg_lift_coast_time_s",  # 2026-only: battery starvation proxy
        "fp2_ers_efficiency_proxy",  # 2026-only: deploy vs recover ratio
        # ── FP3 (standard weekends → NaN in sprint races) ─────────────────────
        "fp3_best_lap_delta",
        "fp3_sector1_delta",
        "fp3_sector2_delta",
        "fp3_sector3_delta",
        "fp3_soft_best_lap_delta",
        "fp3_vs_fp2_soft_improvement",
        "fp3_s1_delta_vs_fp2",
        "fp3_s2_delta_vs_fp2",
        "fp3_s3_delta_vs_fp2",
        "fp3_is_true_qualy_sim",
        "fp3_track_evolution_s",
        # ── Sprint sessions (sprint weekends → NaN for standard) ──────────────
        "sq_best_lap_delta",
        "sq_sector1_delta",
        "sq_sector2_delta",
        "sq_sector3_delta",
        "sq_speed_trap_delta",
        "s_finish_position",
        "s_positions_gained",
        "s_classified",
        # ── Qualifying (always available) ─────────────────────────────────────
        "grid_position",
        "is_front_row",
        "started_top_10",
        "q3_delta_to_pole",
        "best_q_delta_to_pole",
        "q3_participation",
        "best_q_vs_fp3_improvement",
        "quali_best_relative_sector",  # categorical → one-hot encoded
        # ── Team / Power Unit (strongest structural feature in 2026) ──────────
        "pu_score",
        "is_works",
        "pu_is_works",  # interaction: works advantage × PU level
        # ── New 2026 specific features ─────────────────────────────────────────
        "has_upgrade_this_weekend",
        "dnf_rate_2026",
        "ers_clipping_penalty_index",
    ]

    # ── Build training dataset ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  F1 {TARGET_RACE['gp']} {TARGET_RACE['year']} — TOP  RACE PREDICTOR")
    print("=" * 60)
    print("\n>>> PHASE 1: Building training set")

    all_races = TRAINING_RACES_2026 + HISTORICAL_MIAMI
    df_train = build_full_training_set(all_races)

    # ── Build Miami 2026 feature matrix (no labels) ───────────────────────────
    print("\n>>> PHASE 2: Building feature matrix")
    df_gp = build_race_features(
        TARGET_RACE["year"],
        TARGET_RACE["gp"],
    )

    if df_gp.empty:
        raise RuntimeError(
            "Could not build {TARGET_RACE['gp']} {TARGET_RACE['year']} features. "
            "Check that FP1/FP2/FP3/Q sessions are loaded in fastf1 cache."
        )

    # ── Validate feature availability ─────────────────────────────────────────
    available_features = [c for c in FEATURE_COLS if c in df_train.columns]
    missing_features = [c for c in FEATURE_COLS if c not in df_train.columns]

    if missing_features:
        print(
            f"\n  WARN — {len(missing_features)} features absent from training "
            f"(will be ignored):"
        )
        for f in missing_features:
            print(f"    · {f}")

    FEATURE_COLS = available_features

    # ── Train ─────────────────────────────────────────────────────────────────
    print("\n>>> PHASE 3: Training XGBRanker")
    model, final_cols = train_model(df_train, FEATURE_COLS)
    print(f"  Model trained successfully — {len(final_cols)} encoded features")

    # ── Predict ───────────────────────────────────────────────────────────────
    print("\n>>> PHASE 4: Predicting {TARGET_RACE['gp']} {TARGET_RACE['year']} Top")
    df_top = predict_top(model, final_cols, df_gp, FEATURE_COLS)

    print(f"\n{'─' * 45}")
    print(f"  🏁  {TARGET_RACE['gp']} {TARGET_RACE['year']} — PREDICTED TOP ")
    print(f"{'─' * 45}")
    print(f"  {'POS':<5} {'DRV':<6} {'TEAM':<25} {'SCORE':>8}")
    print(f"  {'─' * 44}")
    for _, row in df_top.iterrows():
        team = str(row.get("Team", "N/A"))[:24]
        print(
            f"  P{int(row['predicted_position']):<4} {row['Driver']:<6} "
            f"{team:<25} {row['rank_score']:>8.3f}"
        )
    print(f"  {'─' * 44}")

    # ── Feature importance ────────────────────────────────────────────────────
    print_feature_importance(model, final_cols, top_n=25)
