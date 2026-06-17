import os
import sys
import importlib
import json
import warnings
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
        os.path.join(os.path.dirname(__file__), "f1-api", "f1_fe.py")
    ),
)
f1_fe = importlib.util.module_from_spec(_spec)
sys.modules["f1_fe"] = f1_fe
_spec.loader.exec_module(f1_fe)

import fastf1

fastf1.Cache.enable_cache("./.f1_cache")

# ─────────────────────────────────────────────────────────────────────────────
# IN-MEMORY SESSION CACHING (10x-50x Speedup)
# ─────────────────────────────────────────────────────────────────────────────
_original_get_session = fastf1.get_session
SESSION_CACHE = {}

def cached_get_session(year, gp, identifier=None, **kwargs):
    key = (year, str(gp), str(identifier))
    if key not in SESSION_CACHE:
        SESSION_CACHE[key] = _original_get_session(year, gp, identifier, **kwargs)
    return SESSION_CACHE[key]

fastf1.get_session = cached_get_session

# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE PROGRESS TRACKER
# ─────────────────────────────────────────────────────────────────────────────
PROGRESS = {
    "status": "idle",
    "message": "System ready",
    "percent": 0
}

def update_progress(status: str, message: str, percent: int):
    PROGRESS["status"] = status
    PROGRESS["message"] = message
    PROGRESS["percent"] = percent
    print(f"[PROGRESS] {status.upper()}: {message} ({percent}%)")

# ─────────────────────────────────────────────────────────────────────────────
# 1. CONFIGURATION LOAD
# ─────────────────────────────────────────────────────────────────────────────
with open("team_mappings.json", "r") as f:
    MAPS = json.load(f)

PU_MAP = MAPS["PU_MAP"]
WORKS_MAP = MAPS["WORKS_MAP"]

# ─────────────────────────────────────────────────────────────────────────────
# 2. CIRCUIT PROFILE DYNAMIC RESOLVER
# ─────────────────────────────────────────────────────────────────────────────
def load_circuit_profile(gp_name: str) -> dict:
    """Loads circuit profile dynamically from circuit_profiles.json."""
    profiles_path = os.path.join(os.path.dirname(__file__), "circuit_profiles.json")
    if os.path.exists(profiles_path):
        try:
            with open(profiles_path, "r") as f:
                profiles = json.load(f)
            # Try exact match
            if gp_name in profiles:
                return profiles[gp_name]
            # Try substring match
            for name, profile in profiles.items():
                if name.lower() in gp_name.lower() or gp_name.lower() in name.lower():
                    return profile
            return profiles.get("default", {})
        except Exception as e:
            print(f"Error loading circuit profiles JSON: {e}")
    return {
        "high_speed_ratio": 0.55,
        "overtaking_difficulty": 0.50,
        "brake_intensity": 0.65,
        "pu_sensitivity": 0.70,
        "street_circuit": 0,
        "traction_zones": 0.60
    }

def add_circuit_context(df: pd.DataFrame, gp_name: str) -> pd.DataFrame:
    """Appends circuit profiles as context features."""
    profile = load_circuit_profile(gp_name)
    for key, val in profile.items():
        df[f"circuit_{key}"] = val
    return df

# ─────────────────────────────────────────────────────────────────────────────
# 3. DYNAMIC TRAINING RACES GENERATOR
# ─────────────────────────────────────────────────────────────────────────────
def get_training_races(year: int, gp: str) -> list[dict]:
    """
    Dynamically identifies suitable training races for a target Grand Prix.
    Includes:
      - All same-season races that occurred before the target GP round (weight 1.0)
      - Historical same-GP races from previous years (Y-1: weight 0.22, Y-2: weight 0.05)
      - Fallback baseline races if training set is too small (e.g. Round 1)
    """
    training_races = []
    
    # 1. Target Event Details
    try:
        target_event = fastf1.get_event(year, gp)
        target_round = target_event["RoundNumber"]
        target_gp_name = target_event["EventName"]
        print(f"[get_training_races] Target Event: {target_gp_name} (Round {target_round})")
    except Exception as e:
        print(f"[get_training_races] ERROR getting target event for {gp} {year}: {e}")
        return []

    # 2. Same-season prior races (Weight = 1.0)
    try:
        sched = fastf1.get_event_schedule(year)
        # Prior rounds in current year (excluding round 0: testing)
        prior_rounds = sched[(sched["RoundNumber"] < target_round) & (sched["RoundNumber"] > 0)]
        now_utc = pd.Timestamp.now(tz="UTC")
        
        for _, row in prior_rounds.iterrows():
            event_date = pd.to_datetime(row["EventDate"])
            if event_date.tz is None:
                event_date = event_date.tz_localize("UTC")
            else:
                event_date = event_date.tz_convert("UTC")
                
            # If the event occurred in the past (adding margin to ensure results exist)
            if event_date + pd.Timedelta(days=2) < now_utc:
                training_races.append({
                    "year": year,
                    "gp": row["EventName"],
                    "weight": 1.0
                })
    except Exception as e:
        print(f"[get_training_races] Error resolving same-season prior races: {e}")

    # 3. Historical GP-specific races (Temporal decay lambda=1.5)
    for offset, weight in [(1, 0.22), (2, 0.05)]:
        prev_year = year - offset
        try:
            prev_event = fastf1.get_event(prev_year, gp)
            if prev_event and prev_event["RoundNumber"] > 0:
                training_races.append({
                    "year": prev_year,
                    "gp": prev_event["EventName"],
                    "weight": weight
                })
        except Exception:
            # Silence warning if a GP did not run in a historical year
            pass

    # 4. Fallback Baseline Races (if training set has fewer than 3 races)
    # We load the final 5 rounds of the previous year
    if len(training_races) < 3:
        print(f"[get_training_races] Low training sample size ({len(training_races)} races). Adding fallback baseline races from {year - 1}.")
        try:
            prev_year = year - 1
            sched_prev = fastf1.get_event_schedule(prev_year)
            sched_prev = sched_prev[sched_prev["RoundNumber"] > 0]
            sched_prev = sched_prev.sort_values("RoundNumber", ascending=False)
            
            added = 0
            for _, row in sched_prev.iterrows():
                if added >= 5:
                    break
                # Avoid duplicates
                if not any(r["year"] == prev_year and r["gp"] == row["EventName"] for r in training_races):
                    training_races.append({
                        "year": prev_year,
                        "gp": row["EventName"],
                        "weight": 0.22
                    })
                    added += 1
        except Exception as e:
            print(f"[get_training_races] Error adding fallback races: {e}")

    print(f"[get_training_races] Resolved {len(training_races)} training races:")
    for r in training_races:
        print(f"  - {r['gp']} {r['year']} (weight: {r['weight']:.2f})")
    return training_races

# ─────────────────────────────────────────────────────────────────────────────
# 4. FEATURE COLUMNS LIST
# ─────────────────────────────────────────────────────────────────────────────
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
    "quali_best_relative_sector",  # categorical → dummy-encoded
    # ── Team / Power Unit (strongest structural feature in 2026) ──────────
    "pu_score",
    "is_works",
    "pu_is_works",  # interaction term
    # ── New 2026 specific features ─────────────────────────────────────────
    "has_upgrade_this_weekend",
    "dnf_rate_2026",
    "ers_clipping_penalty_index",
]

# ─────────────────────────────────────────────────────────────────────────────
# 5. FEATURE EXTRACTION HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def safe_merge(base: pd.DataFrame, df: pd.DataFrame, on: str = "Driver") -> pd.DataFrame:
    """Defensive merge — if df is empty or None, returns base unchanged."""
    if df is None or df.empty:
        return base
    cols = [c for c in df.columns if c not in base.columns or c == on]
    return base.merge(df[cols], on=on, how="left")

def get_base_drivers(year: int, gp: str) -> pd.DataFrame:
    """Loads driver list from session results table."""
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
# 6. PRACTICES/QUALIFYING EXTRACTORS
# ─────────────────────────────────────────────────────────────────────────────
def extract_fp1_features(year: int, gp: str) -> pd.DataFrame:
    print(f"    [FP1] Extracting features for {gp} {year}")
    dfs = []
    for fn, kwargs, label in [
        (f1_fe.get_best_lap_delta, {"session_type": "FP1"}, "best_lap_delta"),
        (f1_fe.get_clean_laps_count, {"session_type": "FP1"}, "clean_laps_count"),
        (f1_fe.get_sector_deltas, {"session_type": "FP1"}, "sector_deltas"),
        (f1_fe.get_max_speed_trap, {"session_type": "FP1"}, "speed_trap"),
        (f1_fe.get_compound_avg, {"session_type": "FP1", "compound": "MEDIUM"}, "compound_medium"),
        (f1_fe.get_laps_on_compound, {"session_type": "FP1", "compound": "HARD"}, "laps_on_hard"),
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
    print(f"    [FP2] Extracting features for {gp} {year}")
    dfs = []
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

    for fn, kwargs, label in [
        (f1_fe.get_fuel_corrected_pace, {"session_type": "FP2", "compound": "MEDIUM"}, "fuel_corrected"),
        (f1_fe.get_pu_deployment_asymmetry, {"session_type": "FP2"}, "pu_asymmetry"),
        (f1_fe.get_speed_trap_variance, {"session_type": "FP2"}, "speed_variance"),
        (f1_fe.get_lift_and_coast_laps, {"session_type": "FP2"}, "lift_coast"),
        (f1_fe.get_ers_efficiency_proxy, {"session_type": "FP2"}, "ers_efficiency"),
    ]:
        try:
            dfs.append(fn(year, gp, **kwargs))
        except Exception as e:
            print(f"      WARN fp2.{label}: {e}")

    if not dfs:
        return pd.DataFrame()
    result = dfs[0]
    for df in dfs[1:]:
        result = safe_merge(result, df)
    return result

def extract_fp3_features(year: int, gp: str) -> pd.DataFrame:
    print(f"    [FP3] Extracting features for {gp} {year}")
    dfs = []
    for fn, kwargs, label in [
        (f1_fe.get_best_lap_delta, {"session_type": "FP3"}, "best_lap_delta"),
        (f1_fe.get_clean_laps_count, {"session_type": "FP3"}, "clean_laps_count"),
        (f1_fe.get_sector_deltas, {"session_type": "FP3"}, "sector_deltas"),
        (f1_fe.get_max_speed_trap, {"session_type": "FP3"}, "speed_trap"),
        (f1_fe.get_qualy_sim_delta, {"session_type": "FP3", "compound": "SOFT"}, "qualy_sim"),
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

    try:
        session_s = fastf1.get_session(year, gp, "S")
        session_s.load(telemetry=False, weather=False, messages=False)
        res = session_s.results
        df_sprint = pd.DataFrame({
            "Driver": res["Abbreviation"],
            "s_finish_position": pd.to_numeric(res["Position"], errors="coerce"),
            "s_grid_position": pd.to_numeric(res["GridPosition"], errors="coerce"),
            "s_positions_gained": (
                pd.to_numeric(res["GridPosition"], errors="coerce")
                - pd.to_numeric(res["Position"], errors="coerce")
            ),
            "s_classified": (res["Status"].str.contains("Finished|Lap", na=False)).astype(int),
        })
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
    print(f"    [TEAM] Extracting features for {gp} {year}")
    try:
        df_team = f1_fe.get_team_info(year, gp, "Q")
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
            "Kick Sauber": "Audi",
            "AlphaTauri": "Racing Bulls",
            "Alfa Romeo": "Audi",
            "Aston Martin Aramco Mercedes": "Aston Martin",
        }
        df_team["Team_norm"] = df_team["Team"].replace(TEAM_NAME_MAP)
        df_team["pu_score"] = df_team["Team_norm"].map(PU_MAP).fillna(2).astype(float)
        df_team["is_works"] = df_team["Team_norm"].map(WORKS_MAP).fillna(0).astype(float)
        df_team["pu_is_works"] = df_team["pu_score"] * df_team["is_works"]
        df_team["has_upgrade_this_weekend"] = (df_team["Team_norm"] == "McLaren").astype(int)
        
        # Reliability DNF map for early season
        DNF_RATE_MAP = {"Audi": 0.25, "Racing Bulls": 0.25, "Alpine": 0.15}
        df_team["dnf_rate_2026"] = df_team["Team_norm"].map(DNF_RATE_MAP).fillna(0.0)
        
        return df_team[[
            "Driver", "Team", "pu_score", "is_works", "pu_is_works", 
            "has_upgrade_this_weekend", "dnf_rate_2026"
        ]]
    except Exception as e:
        print(f"      WARN team_features: {e}")
        return pd.DataFrame()

# ─────────────────────────────────────────────────────────────────────────────
# 7. FEATURE MATRIX BUILDER
# ─────────────────────────────────────────────────────────────────────────────
def build_race_features(year: int, gp: str, include_circuit_context: bool = True) -> pd.DataFrame:
    """Assembles full feature matrix for a specific Grand Prix."""
    try:
        event = fastf1.get_event(year, gp)
        # Check event format to identify sprint weekends
        event_format = event.get_session_name(4)
        is_sprint = event_format == "Sprint"
    except Exception:
        is_sprint = False

    print(f"\n  Building features: {gp} {year} ({'Sprint' if is_sprint else 'Standard'} weekend)")
    
    base = get_base_drivers(year, gp)
    if base.empty:
        print(f"  ERROR: Could not load driver list for {gp} {year}")
        return pd.DataFrame()

    base = safe_merge(base, extract_fp1_features(year, gp))

    if is_sprint:
        base = safe_merge(base, extract_sprint_features(year, gp))
    else:
        base = safe_merge(base, extract_fp2_features(year, gp))
        base = safe_merge(base, extract_fp3_features(year, gp))

    base = safe_merge(base, extract_quali_features(year, gp))
    base = safe_merge(base, extract_team_features(year, gp))

    if include_circuit_context:
        base = add_circuit_context(base, gp)

    # Derived interactive features
    if "fp2_ers_efficiency_proxy" in base.columns and "fp2_pu_asymmetry_delta" in base.columns:
        asymmetry_risk = np.where(base["fp2_pu_asymmetry_delta"] < 0, np.abs(base["fp2_pu_asymmetry_delta"]), 0)
        inefficiency_risk = np.where(base["fp2_ers_efficiency_proxy"] < 0, np.abs(base["fp2_ers_efficiency_proxy"]), 0)
        base["ers_clipping_penalty_index"] = asymmetry_risk * inefficiency_risk
    else:
        base["ers_clipping_penalty_index"] = np.nan

    print(f"  → {len(base)} drivers, {len(base.columns)} raw columns")
    return base

# ─────────────────────────────────────────────────────────────────────────────
# 8. LABELS AND DATASET CONSTRUCTOR
# ─────────────────────────────────────────────────────────────────────────────
def get_race_labels(year: int, gp: str) -> pd.DataFrame:
    """Extracts finishing positions and transforms them to labels (higher is better)."""
    try:
        session = fastf1.get_session(year, gp, "R")
        session.load(telemetry=False, weather=False, messages=False)
        res = session.results

        df = pd.DataFrame({
            "Driver": res["Abbreviation"],
            "finish_pos": pd.to_numeric(res["Position"], errors="coerce").fillna(22),
            "status": res["Status"],
        })

        # Penalize DNFs/DNS
        crash_keywords = "Accident|Collision|Spun off|Damage"
        crash_mask = df["status"].str.contains(crash_keywords, na=False, case=False)
        df.loc[crash_mask, "finish_pos"] = 22
        
        dnf_mask = ~df["status"].str.contains("Finished|Lap", na=False)
        df.loc[dnf_mask, "finish_pos"] = 22

        # Transform (P1 -> 21, P2 -> 20... DNF -> 0)
        df["label"] = (22 - df["finish_pos"]).clip(lower=0).astype(int)
        return df[["Driver", "finish_pos", "label"]]
    except Exception as e:
        print(f"  ERROR loading labels for {gp} {year}: {e}")
        return pd.DataFrame()

def build_full_training_set(races: list[dict]) -> pd.DataFrame:
    all_dfs = []
    N = len(races)
    for i, race in enumerate(races):
        percent = 15 + int((i / N) * 60)
        msg = f"Extracting features: {race['gp']} {race['year']} ({i+1}/{N})"
        update_progress("feature_engineering", msg, percent)

        print(f"\nProcessing training GP: {race['gp']} {race['year']} (weight={race['weight']:.2f})")
        features = build_race_features(race["year"], race["gp"], include_circuit_context=True)
        if features.empty:
            continue
        labels = get_race_labels(race["year"], race["gp"])
        if labels.empty:
            continue
        df = features.merge(labels, on="Driver", how="left")
        df = df.dropna(subset=["label"])
        df["label"] = df["label"].astype(int)
        df["sample_weight"] = race["weight"]
        df["is_2026"] = int(race["year"] == 2026)
        all_dfs.append(df)

    if not all_dfs:
        raise ValueError("No races with valid training data available.")
    return pd.concat(all_dfs, axis=0, ignore_index=True)

# ─────────────────────────────────────────────────────────────────────────────
# 9. PREPROCESSING & TRAINING
# ─────────────────────────────────────────────────────────────────────────────
def preprocess(df: pd.DataFrame, feature_cols: list[str], known_cols: list[str] = None) -> tuple[pd.DataFrame, list[str]]:
    cat_cols = [c for c in feature_cols if c in df.columns and df[c].dtype == object]
    
    # Pad missing columns with NaN
    for col in feature_cols:
        if col not in df.columns:
            df[col] = np.nan

    df_enc = pd.get_dummies(df[feature_cols], columns=cat_cols, drop_first=True)
    df_enc = df_enc.apply(pd.to_numeric, errors="coerce")
    df_enc = df_enc.select_dtypes(include=[np.number])

    if known_cols is not None:
        # Align inference columns to training schema
        for col in known_cols:
            if col not in df_enc.columns:
                df_enc[col] = 0.0
        df_enc = df_enc[known_cols]

    final_cols = df_enc.columns.tolist()
    return df_enc, final_cols

def train_model(df_train: pd.DataFrame, feature_cols: list[str]):
    df_train = df_train.sort_values(["year", "gp"]).reset_index(drop=True)
    X_raw = df_train[feature_cols]
    y = df_train["label"].values.astype(int)

    X_proc, final_cols = preprocess(X_raw, feature_cols)
    
    # Build XGBRanker query groups
    race_order = df_train[["year", "gp"]].drop_duplicates()
    groups = []
    group_weights = []

    for _, row in race_order.iterrows():
        mask = (df_train["year"] == row["year"]) & (df_train["gp"] == row["gp"])
        groups.append(mask.sum())
        group_weights.append(df_train.loc[mask, "sample_weight"].iloc[0])

    print(f"\n[train] query groups: {groups}, weights: {group_weights}")

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
    model.fit(X_proc, y, group=groups, sample_weight=group_weights)
    return model, final_cols

# ─────────────────────────────────────────────────────────────────────────────
# 10. DYNAMIC EXECUTION INTERFACE (GET OR TRAIN)
# ─────────────────────────────────────────────────────────────────────────────
def train_and_predict_for_race(year: int, gp: str) -> pd.DataFrame:
    """
    Orchestrates dynamic model retrieval/training and runs predictions.
    Saves and loads trained models from cache to ensure performance.
    """
    update_progress("preparing", "Initializing neural model setup...", 5)
    
    # Clean GP Name
    try:
        event = fastf1.get_event(year, gp)
        gp_clean = event["EventName"]
    except Exception:
        gp_clean = gp

    cache_dir = "./.f1_cache"
    os.makedirs(cache_dir, exist_ok=True)
    
    # Safe model filename
    safe_gp_name = gp_clean.replace(" ", "_").replace("'", "").lower()
    model_path = os.path.join(cache_dir, f"model_{year}_{safe_gp_name}.pkl")
    
    import pickle
    model = None
    final_cols = None
    available_features = None

    # Try loading cached model
    if os.path.exists(model_path):
        print(f"[f1_model] Loading cached model for {gp_clean} {year} from disk...")
        try:
            with open(model_path, "rb") as f:
                saved = pickle.load(f)
                model = saved["model"]
                final_cols = saved["final_cols"]
                available_features = saved["features"]
            update_progress("cached", f"Loaded cached model for {gp_clean}!", 100)
        except Exception as e:
            print(f"[f1_model] Failed to load cached model: {e}")

    if model is None:
        print(f"[f1_model] Re-training model dynamically for {gp_clean} {year}...")
        update_progress("scheduling", "Analyzing F1 calendar schedule...", 10)
        # Determine training races
        races = get_training_races(year, gp_clean)
        if not races:
            raise ValueError(f"No suitable training races identified for {gp_clean} {year}")

        df_train = build_full_training_set(races)
        available_features = [c for c in FEATURE_COLS if c in df_train.columns]
        
        update_progress("training", "Fitting XGBoost pairwise ranking model...", 80)
        model, final_cols = train_model(df_train, available_features)
        
        # Cache to disk
        print(f"[f1_model] Saving trained model to {model_path}...")
        try:
            with open(model_path, "wb") as f:
                pickle.dump({
                    "model": model,
                    "final_cols": final_cols,
                    "features": available_features
                }, f)
        except Exception as e:
            print(f"[f1_model] Failed to cache model: {e}")

    # Build features for inference GP
    update_progress("inference", f"Building dynamic features for {gp_clean}...", 90)
    df_gp = build_race_features(year, gp_clean, include_circuit_context=True)
    if df_gp.empty:
        raise RuntimeError(f"Could not build features for inference target {gp_clean} {year}")

    # Run inference
    update_progress("inference", f"Running telemetry inference on {gp_clean}...", 95)
    df_inference = df_gp.copy()
    for col in available_features:
        if col not in df_inference.columns:
            df_inference[col] = np.nan

    X_raw = df_inference[available_features]
    X_proc, _ = preprocess(X_raw, available_features, known_cols=final_cols)
    
    scores = model.predict(X_proc)
    
    update_progress("complete", "Telemetry analysis finished!", 100)

    df_result = df_gp[["Driver"]].copy()
    if "Team" in df_gp.columns:
        df_result["Team"] = df_gp["Team"].values

    df_result["rank_score"] = scores
    df_result = df_result.sort_values("rank_score", ascending=False).reset_index(drop=True)
    df_result["predicted_position"] = df_result.index + 1
    
    # Reset to idle
    update_progress("idle", "Ready", 0)
    
    return df_result
