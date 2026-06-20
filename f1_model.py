import os
import sys
import importlib
import json
import warnings
import contextlib
import io
import numpy as np
import pandas as pd
from xgboost import XGBRanker
from scipy.stats import spearmanr

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

TEAM_NORM_MAP = {
    "Mercedes-AMG Petronas F1 Team": "Mercedes",
    "McLaren F1 Team":               "McLaren",
    "Scuderia Ferrari":              "Ferrari",
    "Williams Racing":               "Williams",
    "BWT Alpine F1 Team":            "Alpine",
    "Aston Martin Aramco F1 Team":   "Aston Martin",
    "Oracle Red Bull Racing":        "Red Bull Racing",
    "Visa Cash App RB F1 Team":      "Racing Bulls",
    "MoneyGram Haas F1 Team":        "Haas",
    "Audi F1 Team":                  "Audi",
    "Cadillac F1 Team":              "Cadillac",
    "Kick Sauber":                   "Audi",
    "AlphaTauri":                    "Racing Bulls",
    "Alfa Romeo":                    "Audi",
    "Aston Martin Aramco Mercedes":  "Aston Martin",
    "Haas F1 Team":                  "Haas",
    "Scuderia AlphaTauri":           "Racing Bulls",
}

UPGRADE_SCORES_BY_GP = {
    "miami": {
        "McLaren": 2, "Ferrari": 2, "Mercedes": 1, "Red Bull Racing": 1,
        "Williams": 1, "Racing Bulls": 1, "Alpine": 0, "Haas": 0,
        "Cadillac": 0, "Aston Martin": 0, "Audi": 0
    },
    "monaco": {
        "McLaren": 2, "Ferrari": 2, "Red Bull Racing": 1, "Audi": 1,
        "Mercedes": 1, "Aston Martin": 1, "Haas": 1, "Racing Bulls": 1,
        "Williams": 1, "Alpine": 0, "Cadillac": 0
    },
    "canada": {
        "McLaren": 3, "Mercedes": 2, "Racing Bulls": 2, "Alpine": 2,
        "Williams": 1, "Haas": 1, "Cadillac": 1, "Red Bull Racing": 0,
        "Ferrari": 0, "Aston Martin": 0, "Audi": 0
    },
    "barcelona": {
        "Ferrari": 2, "Red Bull Racing": 2, "Racing Bulls": 2, "McLaren": 1,
        "Mercedes": 1, "Williams": 1, "Cadillac": 1, "Haas": 1,
        "Aston Martin": 0, "Alpine": 0, "Audi": 0
    },
    "spain": {
        "Ferrari": 2, "Red Bull Racing": 2, "Racing Bulls": 2, "McLaren": 1,
        "Mercedes": 1, "Williams": 1, "Cadillac": 1, "Haas": 1,
        "Aston Martin": 0, "Alpine": 0, "Audi": 0
    }
}

UPGRADE_DESC = {
    3: "Major rebuild — floor+chassis+wings+bodywork",
    2: "Significant — floor / front wing",
    1: "Minor — cooling / aero tweaks",
    0: "No performance upgrades",
}

UPGRADE_SIGMA_PER_POINT = 0.18
GRID_ANCHOR_WEIGHT = 0.30
SPRINT_BOOST_SIGMA = 0.20

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
    "fp1_best_lap_delta", "fp1_clean_laps_count",
    "fp1_sector1_delta", "fp1_sector2_delta", "fp1_sector3_delta",
    "fp1_max_speed_trap", "fp1_speed_trap_delta",
    "fp1_compound_medium_avg", "fp1_laps_on_hard",
    "fp1_vs_teammate",
    "fp2_best_lap_delta", "fp2_clean_laps_count",
    "fp2_sector1_delta", "fp2_sector2_delta", "fp2_sector3_delta",
    "fp2_max_speed_trap",
    "fp2_longrun_medium_avg_pace", "fp2_longrun_medium_deg_rate",
    "fp2_longrun_medium_deg_total", "fp2_longrun_medium_consistency",
    "fp2_longrun_hard_avg_pace", "fp2_longrun_hard_deg_rate",
    "fp2_medium_fuel_corrected_pace",
    "fp2_pu_asymmetry_delta", "fp2_speed_trap_std_kmh",
    "fp2_avg_lift_coast_time_s", "fp2_ers_efficiency_proxy",
    "fp3_best_lap_delta",
    "fp3_sector1_delta", "fp3_sector2_delta", "fp3_sector3_delta",
    "fp3_soft_best_lap_delta", "fp3_vs_fp2_soft_improvement",
    "fp3_s1_delta_vs_fp2", "fp3_s2_delta_vs_fp2", "fp3_s3_delta_vs_fp2",
    "fp3_is_true_qualy_sim", "fp3_track_evolution_s",
    "sq_best_lap_delta",
    "sq_sector1_delta", "sq_sector2_delta", "sq_sector3_delta",
    "sq_speed_trap_delta",
    "sq_vs_teammate",
    "s_finish_position", "s_positions_gained", "s_classified",
    "grid_position", "is_front_row", "started_top_10",
    "q3_delta_to_pole", "best_q_delta_to_pole", "q3_participation",
    "best_q_vs_fp3_improvement", "quali_best_relative_sector",
    "pu_score", "is_works", "pu_is_works",
    "ers_clipping_penalty_index",
    "recent_form_avg", "recent_form_wins",
    "team_2026_pace_rank",
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

def load_parquet_cache(year: int, gp: str, session: str) -> pd.DataFrame | None:
    cache_path = os.path.join(
        ".f1_cache",
        "parquet",
        f"year={year}",
        f"gp={gp}",
        f"session={session}.parquet"
    )
    if os.path.exists(cache_path):
        try:
            df = pd.read_parquet(cache_path)
            print(f"    [CACHE] Loaded {session} features from Parquet cache")
            return df
        except Exception as e:
            print(f"    [CACHE] Error loading Parquet cache for {session}: {e}")
    return None

def save_parquet_cache(df: pd.DataFrame, year: int, gp: str, session: str) -> None:
    if df is None:
        return
    cache_dir = os.path.join(
        ".f1_cache",
        "parquet",
        f"year={year}",
        f"gp={gp}"
    )
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"session={session}.parquet")
    try:
        df.to_parquet(cache_path, compression="snappy")
        print(f"    [CACHE] Saved {session} features to Parquet cache")
    except Exception as e:
        print(f"    [CACHE] Error saving Parquet cache for {session}: {e}")

def get_base_drivers(year: int, gp: str) -> pd.DataFrame:
    """Loads driver list from session results table."""
    df_cached = load_parquet_cache(year, gp, "base")
    if df_cached is not None:
        return df_cached
    for session_type in ["Q", "SQ", "R", "S"]:
        try:
            s = fastf1.get_session(year, gp, session_type)
            s.load(telemetry=False, weather=False, messages=False)
            drivers = s.results["Abbreviation"].tolist()
            if drivers:
                df = pd.DataFrame({"Driver": drivers, "year": year, "gp": gp})
                save_parquet_cache(df, year, gp, "base")
                return df
        except Exception:
            continue
    return pd.DataFrame()

# ─────────────────────────────────────────────────────────────────────────────
# 6. PRACTICES/QUALIFYING EXTRACTORS
# ─────────────────────────────────────────────────────────────────────────────
def extract_fp1_features(year: int, gp: str) -> pd.DataFrame:
    df_cached = load_parquet_cache(year, gp, "fp1")
    if df_cached is not None:
        return df_cached
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
        result = pd.DataFrame()
        save_parquet_cache(result, year, gp, "fp1")
        return result
    result = dfs[0]
    for df in dfs[1:]:
        result = safe_merge(result, df)
    save_parquet_cache(result, year, gp, "fp1")
    return result

def extract_fp2_features(year: int, gp: str) -> pd.DataFrame:
    df_cached = load_parquet_cache(year, gp, "fp2")
    if df_cached is not None:
        return df_cached
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
        result = pd.DataFrame()
        save_parquet_cache(result, year, gp, "fp2")
        return result
    result = dfs[0]
    for df in dfs[1:]:
        result = safe_merge(result, df)
    save_parquet_cache(result, year, gp, "fp2")
    return result

def extract_fp3_features(year: int, gp: str) -> pd.DataFrame:
    df_cached = load_parquet_cache(year, gp, "fp3")
    if df_cached is not None:
        return df_cached
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
        result = pd.DataFrame()
        save_parquet_cache(result, year, gp, "fp3")
        return result
    result = dfs[0]
    for df in dfs[1:]:
        result = safe_merge(result, df)
    save_parquet_cache(result, year, gp, "fp3")
    return result

def extract_sprint_features(year: int, gp: str) -> pd.DataFrame:
    df_cached = load_parquet_cache(year, gp, "sprint")
    if df_cached is not None:
        return df_cached
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
        result = pd.DataFrame()
        save_parquet_cache(result, year, gp, "sprint")
        return result
    result = dfs[0]
    for df in dfs[1:]:
        result = safe_merge(result, df)
    save_parquet_cache(result, year, gp, "sprint")
    return result

def extract_quali_features(year: int, gp: str) -> pd.DataFrame:
    df_cached = load_parquet_cache(year, gp, "quali")
    if df_cached is not None:
        return df_cached
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
        result = pd.DataFrame()
        save_parquet_cache(result, year, gp, "quali")
        return result
    result = dfs[0]
    for df in dfs[1:]:
        result = safe_merge(result, df)
    save_parquet_cache(result, year, gp, "quali")
    return result

def extract_team_features(year: int, gp: str) -> pd.DataFrame:
    df_cached = load_parquet_cache(year, gp, "team")
    if df_cached is not None:
        return df_cached
    print(f"    [TEAM] Extracting features for {gp} {year}")
    try:
        df_team = f1_fe.get_team_info(year, gp, "Q")
        df_team["Team_norm"] = df_team["Team"].replace(TEAM_NORM_MAP).fillna(df_team["Team"])
        df_team["pu_score"] = df_team["Team_norm"].map(PU_MAP).fillna(2).astype(float)
        df_team["is_works"] = df_team["Team_norm"].map(WORKS_MAP).fillna(0).astype(float)
        df_team["pu_is_works"] = df_team["pu_score"] * df_team["is_works"]
        result = df_team[["Driver", "Team", "pu_score", "is_works", "pu_is_works"]]
        save_parquet_cache(result, year, gp, "team")
        return result
    except Exception as e:
        print(f"      WARN team_features: {e}")
        result = pd.DataFrame()
        save_parquet_cache(result, year, gp, "team")
        return result

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
# 10. HYPERPARAMETER CALIBRATION, POST-PREDICTIONS & LOO-CV
# ─────────────────────────────────────────────────────────────────────────────

@contextlib.contextmanager
def silent():
    with contextlib.redirect_stdout(io.StringIO()):
        yield


def discover_2026_races_before_target(target_gp: str, fallback: list[dict] = None) -> list[dict]:
    try:
        schedule = fastf1.get_event_schedule(2026, include_testing=False)
        target_mask = schedule["EventName"].str.contains(target_gp, case=False, na=False)
        if not target_mask.any():
            target_mask = schedule["Country"].str.contains(target_gp, case=False, na=False)
        if not target_mask.any():
            raise ValueError(f"'{target_gp}' not found in the 2026 calendar")
        target_round = schedule.loc[target_mask, "RoundNumber"].iloc[0]
        prior = schedule[schedule["RoundNumber"] < target_round]
        return [{"year": 2026, "gp": row["EventName"], "weight": 1.0}
                for _, row in prior.iterrows()]
    except Exception as exc:
        print(f"Discovery failed ({exc}) — using fallback")
        return fallback or []


def discover_full_season(year: int, weight: float) -> list[dict]:
    try:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
        return [
            {"year": year, "gp": row["EventName"], "weight": weight}
            for _, row in schedule.iterrows()
        ]
    except Exception:
        return []


def get_quali_grid_position(year: int, gp: str) -> pd.DataFrame:
    for stype in ["Q", "SQ"]:
        try:
            s = fastf1.get_session(year, gp, stype)
            s.load(telemetry=False, weather=False, messages=False)
            res = s.results[["Abbreviation", "Position"]].copy()
            res.columns = ["Driver", "grid_position"]
            res["grid_position"] = pd.to_numeric(res["grid_position"], errors="coerce")
            if res["grid_position"].notna().any():
                res["is_front_row"]   = (res["grid_position"] <= 2).astype(int)
                res["started_top_10"] = (res["grid_position"] <= 10).astype(int)
                return res
        except Exception:
            continue
    try:
        s = fastf1.get_session(year, gp, "R")
        s.load(telemetry=False, weather=False, messages=False)
        res = s.results[["Abbreviation", "GridPosition"]].copy()
        res.columns = ["Driver", "grid_position"]
        res["grid_position"] = pd.to_numeric(res["grid_position"], errors="coerce")
        res["is_front_row"]   = (res["grid_position"] <= 2).astype(int)
        res["started_top_10"] = (res["grid_position"] <= 10).astype(int)
        return res
    except Exception:
        return pd.DataFrame()


def get_season_form(labels_list: list[pd.DataFrame]) -> pd.DataFrame:
    if not labels_list:
        return pd.DataFrame()
    combined = pd.concat(labels_list, ignore_index=True)
    return (
        combined.groupby("Driver")["finish_pos"]
        .agg(
            recent_form_avg="mean",
            recent_form_wins=lambda x: int((x == 1).sum()),
        )
        .reset_index()
    )


def get_team_pace_rank(labels_list: list[pd.DataFrame], features_list: list[pd.DataFrame]) -> pd.DataFrame:
    if not labels_list or not features_list:
        return pd.DataFrame()
    driver_team_dfs = [
        f[["Driver", "Team"]].copy()
        for f in features_list if "Team" in f.columns
    ]
    if not driver_team_dfs:
        return pd.DataFrame()
    driver_team = (
        pd.concat(driver_team_dfs, ignore_index=True)
        .drop_duplicates("Driver", keep="last")
    )
    driver_team["Team_norm"] = driver_team["Team"].replace(TEAM_NORM_MAP).fillna(driver_team["Team"])
    combined = (
        pd.concat(labels_list, ignore_index=True)
        .merge(driver_team[["Driver", "Team_norm"]], on="Driver", how="left")
    )
    return (
        combined.groupby("Team_norm")["finish_pos"].mean()
        .reset_index()
        .rename(columns={"finish_pos": "team_2026_pace_rank"})
    )


def add_teammate_deltas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for prefix in ["fp1", "sq"]:
        src = f"{prefix}_best_lap_delta"
        dst = f"{prefix}_vs_teammate"
        df[dst] = np.nan
        if src not in df.columns or "Team" not in df.columns:
            continue
        for _, group in df.groupby("Team"):
            if len(group) < 2:
                continue
            for idx in group.index:
                my_val = df.at[idx, src]
                others = group.loc[group.index != idx, src].dropna()
                if pd.notna(my_val) and len(others) > 0:
                    df.at[idx, dst] = float(my_val) - float(others.mean())
    return df


def predict_top(model, final_cols: list[str], df_gp: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    df_inference = df_gp.copy()
    for col in feature_cols:
        if col not in df_inference.columns:
            df_inference[col] = np.nan
    X_raw = df_inference[feature_cols]
    X_proc, _ = preprocess(X_raw, feature_cols, known_cols=final_cols)
    scores = model.predict(X_proc)
    
    df_result = df_gp.copy()
    df_result["rank_score"] = scores
    df_result = df_result.sort_values("rank_score", ascending=False).reset_index(drop=True)
    df_result["predicted_position"] = df_result.index + 1
    return df_result


def apply_upgrade_adjustment(df_pred: pd.DataFrame, target_gp: str, upgrade_sigma: float | None = None) -> pd.DataFrame:
    sigma = upgrade_sigma if upgrade_sigma is not None else UPGRADE_SIGMA_PER_POINT
    df = df_pred.copy()
    df["Team_norm"] = df["Team"].replace(TEAM_NORM_MAP).fillna(df["Team"])
    
    gp_key = target_gp.replace(" ", "").replace("'", "").lower()
    matched_gp = None
    for key in UPGRADE_SCORES_BY_GP:
        if key in gp_key or gp_key in key:
            matched_gp = key
            break
            
    upgrade_map = UPGRADE_SCORES_BY_GP.get(matched_gp, {}) if matched_gp else {}
    df["upgrade_score"] = df["Team_norm"].map(upgrade_map).fillna(0)
    score_std = df["rank_score"].std()
    df["upgrade_boost"] = df["upgrade_score"] * sigma * score_std
    df["adjusted_score"] = df["rank_score"] + df["upgrade_boost"]
    df = df.sort_values("adjusted_score", ascending=False).reset_index(drop=True)
    df["adjusted_position"] = df.index + 1
    return df


def apply_grid_anchor(df_pred: pd.DataFrame, year: int, gp: str, anchor_weight: float | None = None) -> pd.DataFrame:
    alpha = anchor_weight if anchor_weight is not None else GRID_ANCHOR_WEIGHT
    df = df_pred.copy()
    
    score_col = "adjusted_score" if "adjusted_score" in df.columns else "rank_score"
    
    if "grid_position" not in df.columns or df["grid_position"].isna().all():
        grid = get_quali_grid_position(year, gp)
        if not grid.empty:
            df = df.merge(grid[["Driver", "grid_position"]], on="Driver", how="left", suffixes=("", "_g"))
            if "grid_position_g" in df.columns:
                df["grid_position"] = df["grid_position"].fillna(df["grid_position_g"])
                df.drop(columns=["grid_position_g"], inplace=True)
                
    n = len(df)
    s = df[score_col].astype(float)
    s_z = (s - s.mean()) / (s.std() + 1e-9)
    
    grid = pd.to_numeric(df.get("grid_position"), errors="coerce")
    median_pos = (n + 1) / 2
    grid_z = (median_pos - grid) / median_pos
    grid_z = grid_z.fillna(0.0)
    
    df["grid_z"] = grid_z
    df["anchored_score"] = (1.0 - alpha) * s_z + alpha * grid_z
    df = df.sort_values("anchored_score", ascending=False).reset_index(drop=True)
    df["anchored_position"] = df.index + 1
    return df


def apply_sprint_adjustment(df_pred: pd.DataFrame, year: int, gp: str, sprint_sigma: float | None = None) -> pd.DataFrame:
    sigma = sprint_sigma if sprint_sigma is not None else SPRINT_BOOST_SIGMA
    try:
        session_s = fastf1.get_session(year, gp, "S")
        session_s.load(telemetry=False, weather=False, messages=False)
        res = session_s.results[["Abbreviation", "Position", "Status"]].copy()
        res.columns = ["Driver", "sprint_pos", "sprint_status"]
        res["sprint_pos"] = pd.to_numeric(res["sprint_pos"], errors="coerce")
    except Exception:
        return df_pred

    df = df_pred.copy()
    df = df.merge(res, on="Driver", how="left")

    n = len(df)
    score_std = df["adjusted_score"].std() if "adjusted_score" in df.columns else df["rank_score"].std()
    median_pos = (n + 1) / 2

    df["sprint_z"] = (median_pos - df["sprint_pos"]) / median_pos
    dnf_mask = ~df["sprint_status"].fillna("").str.contains("Finished|Lap", na=False)
    df.loc[dnf_mask, "sprint_z"] = -1.0
    df["sprint_z"] = df["sprint_z"].fillna(0.0)

    df["sprint_boost"] = df["sprint_z"] * sigma * score_std
    score_col = "adjusted_score" if "adjusted_score" in df.columns else "rank_score"
    df["sprint_adjusted_score"] = df[score_col] + df["sprint_boost"]

    df = df.sort_values("sprint_adjusted_score", ascending=False).reset_index(drop=True)
    df["sprint_adjusted_position"] = df.index + 1
    return df


def calibrate_params(race_cache: list[dict], feature_cols: list[str], target_gp: str) -> tuple[float, float]:
    test_races = [
        e for e in race_cache
        if e["race"]["year"] == 2026
        and not e["labels"].empty
        and "grid_position" in e["features"].columns
        and e["race"]["gp"] != target_gp
    ]

    if len(test_races) < 2:
        return UPGRADE_SIGMA_PER_POINT, GRID_ANCHOR_WEIGHT

    upgrade_sigmas = [0.10, 0.15, 0.18, 0.20, 0.25]
    anchor_weights = [0.00, 0.15, 0.25, 0.30, 0.40, 0.55]
    best_rho = -np.inf
    best_u, best_a = UPGRADE_SIGMA_PER_POINT, GRID_ANCHOR_WEIGHT
    grid_results = {}

    fold_preds = {}
    for entry in test_races:
        train_parts = [e["df"] for e in race_cache if e is not entry]
        if not train_parts:
            fold_preds[id(entry)] = None
            continue
        df_cv = pd.concat(train_parts, ignore_index=True)
        avail = [c for c in feature_cols if c in df_cv.columns]
        try:
            with silent():
                m, cols = train_model(df_cv, avail)
                fold_preds[id(entry)] = predict_top(m, cols, entry["features"], avail)
        except Exception:
            fold_preds[id(entry)] = None

    for u_sigma in upgrade_sigmas:
        for a_weight in anchor_weights:
            rhos = []
            for entry in test_races:
                df_pred = fold_preds.get(id(entry))
                if df_pred is None:
                    continue
                try:
                    with silent():
                        df_adj = apply_upgrade_adjustment(df_pred, entry["race"]["gp"], upgrade_sigma=u_sigma)
                        df_anc = apply_grid_anchor(df_adj, entry["race"]["year"], entry["race"]["gp"], anchor_weight=a_weight)
                except Exception:
                    continue
                df_eval = df_anc.merge(entry["labels"][["Driver", "finish_pos"]], on="Driver", how="inner")
                if len(df_eval) >= 5:
                    rho, _ = spearmanr(df_eval["anchored_position"], df_eval["finish_pos"])
                    rhos.append(rho)
            if rhos:
                mean_rho = float(np.mean(rhos))
                grid_results[(u_sigma, a_weight)] = mean_rho
                if mean_rho > best_rho:
                    best_rho = mean_rho
                    best_u, best_a = u_sigma, a_weight
    return best_u, best_a


def calibrate_sigma(race_cache: list[dict], feature_cols: list[str], target_gp: str) -> tuple[float, float]:
    test_races = [
        e for e in race_cache
        if e["race"]["year"] == 2026
        and not e["labels"].empty
        and "s_finish_position" in e["features"].columns
        and e["race"]["gp"] != target_gp
    ]

    if len(test_races) < 2:
        return UPGRADE_SIGMA_PER_POINT, SPRINT_BOOST_SIGMA

    upgrade_sigmas = [0.10, 0.15, 0.18, 0.20, 0.25]
    sprint_sigmas  = [0.10, 0.15, 0.20, 0.25, 0.30]
    best_rho = -np.inf
    best_u, best_s = UPGRADE_SIGMA_PER_POINT, SPRINT_BOOST_SIGMA
    grid_results = {}

    fold_preds = {}
    for entry in test_races:
        train_parts = [e["df"] for e in race_cache if e is not entry]
        if not train_parts:
            fold_preds[id(entry)] = None
            continue
        df_cv = pd.concat(train_parts, ignore_index=True)
        avail = [c for c in feature_cols if c in df_cv.columns]
        try:
            with silent():
                m, cols = train_model(df_cv, avail)
                fold_preds[id(entry)] = predict_top(m, cols, entry["features"], avail)
        except Exception:
            fold_preds[id(entry)] = None

    for u_sigma in upgrade_sigmas:
        for s_sigma in sprint_sigmas:
            rhos = []
            for entry in test_races:
                df_pred = fold_preds.get(id(entry))
                if df_pred is None:
                    continue
                try:
                    with silent():
                        df_adj = apply_upgrade_adjustment(df_pred, entry["race"]["gp"], upgrade_sigma=u_sigma)
                        df_spr = apply_sprint_adjustment(df_adj, entry["race"]["year"], entry["race"]["gp"], sprint_sigma=s_sigma)
                except Exception:
                    continue
                df_eval = df_spr.merge(entry["labels"][["Driver", "finish_pos"]], on="Driver", how="inner")
                if len(df_eval) >= 5:
                    rho, _ = spearmanr(df_eval["sprint_adjusted_position"], df_eval["finish_pos"])
                    rhos.append(rho)
            if rhos:
                mean_rho = float(np.mean(rhos))
                grid_results[(u_sigma, s_sigma)] = mean_rho
                if mean_rho > best_rho:
                    best_rho = mean_rho
                    best_u, best_s = u_sigma, s_sigma
    return best_u, best_s


def evaluate_loo_cv(race_cache: list[dict], feature_cols: list[str]) -> None:
    test_entries = [
        e for e in race_cache
        if e["race"]["year"] == 2026
        and not e["labels"].empty
    ]
    if not test_entries:
        print("[LOO-CV] No completed 2026 races for evaluation.")
        return
    print(f"\n[LOO-CV] Running Leave-One-Out CV on {len(test_entries)} races...")
    spearman_vals = []
    for entry in test_entries:
        train_parts = [e["df"] for e in race_cache if e is not entry]
        if not train_parts:
            continue
        df_cv = pd.concat(train_parts, ignore_index=True)
        avail = [c for c in feature_cols if c in df_cv.columns]
        try:
            with silent():
                m, cols = train_model(df_cv, avail)
                df_pred = predict_top(m, cols, entry["features"], avail)
                is_sprint = "s_finish_position" in entry["features"].columns
                if is_sprint:
                    df_pred = apply_upgrade_adjustment(df_pred, entry["race"]["gp"])
                    df_final = apply_sprint_adjustment(df_pred, entry["race"]["year"], entry["race"]["gp"])
                    pos_col = "sprint_adjusted_position"
                else:
                    df_pred = apply_upgrade_adjustment(df_pred, entry["race"]["gp"])
                    df_final = apply_grid_anchor(df_pred, entry["race"]["year"], entry["race"]["gp"])
                    pos_col = "anchored_position"
            
            df_eval = df_final.merge(entry["labels"][["Driver", "finish_pos"]], on="Driver", how="inner")
            if len(df_eval) >= 5:
                rho, _ = spearmanr(df_eval[pos_col], df_eval["finish_pos"])
                spearman_vals.append(rho)
                print(f"  Round: {entry['race']['gp']} {entry['race']['year']} -> Spearman rho: {rho:+.3f}")
        except Exception as exc:
            print(f"  Round: {entry['race']['gp']} {entry['race']['year']} -> CV Fold failed: {exc}")
    if spearman_vals:
        print(f"  Mean Spearman rho: {np.mean(spearman_vals):.3f} ± {np.std(spearman_vals):.3f}")


def ablation_study(race_cache: list[dict], feature_cols: list[str]) -> None:
    test_entries = [
        e for e in race_cache
        if e["race"]["year"] == 2026
        and not e["labels"].empty
    ]
    if not test_entries:
        print("[Ablation] No completed 2026 races for study.")
        return
    
    variants = {
        "Base only": [],
        "+ Upgrade": [],
        "+ Sprint/Anchor": [],
        "All combined": []
    }
    
    for entry in test_entries:
        train_parts = [e["df"] for e in race_cache if e is not entry]
        if not train_parts:
            continue
        df_cv = pd.concat(train_parts, ignore_index=True)
        avail = [c for c in feature_cols if c in df_cv.columns]
        try:
            with silent():
                m, cols = train_model(df_cv, avail)
                df_pred = predict_top(m, cols, entry["features"], avail)
                is_sprint = "s_finish_position" in entry["features"].columns
                
                df_base = df_pred.sort_values("rank_score", ascending=False).reset_index(drop=True)
                df_base["base_pos"] = df_base.index + 1
                
                df_upg = apply_upgrade_adjustment(df_pred, entry["race"]["gp"])
                
                if is_sprint:
                    df_spr_only = apply_sprint_adjustment(df_pred, entry["race"]["year"], entry["race"]["gp"])
                    spr_pos_col = "sprint_adjusted_position"
                else:
                    df_spr_only = apply_grid_anchor(df_pred, entry["race"]["year"], entry["race"]["gp"])
                    spr_pos_col = "anchored_position"
                    
                if is_sprint:
                    df_all = apply_sprint_adjustment(df_upg, entry["race"]["year"], entry["race"]["gp"])
                    all_pos_col = "sprint_adjusted_position"
                else:
                    df_all = apply_grid_anchor(df_upg, entry["race"]["year"], entry["race"]["gp"])
                    all_pos_col = "anchored_position"
            
            for key, df_v, pos_col in [
                ("Base only", df_base, "base_pos"),
                ("+ Upgrade", df_upg, "adjusted_position"),
                ("+ Sprint/Anchor", df_spr_only, spr_pos_col),
                ("All combined", df_all, all_pos_col)
            ]:
                df_eval = df_v.merge(entry["labels"][["Driver", "finish_pos"]], on="Driver", how="inner")
                if len(df_eval) >= 5:
                    rho, _ = spearmanr(df_eval[pos_col], df_eval["finish_pos"])
                    variants[key].append(rho)
        except Exception:
            continue
            
    print("\n[Ablation] Mean Spearman rho by variant:")
    for key, vals in variants.items():
        if vals:
            print(f"  {key:<18} : {np.mean(vals):+.3f}")


# ─────────────────────────────────────────────────────────────────────────────
# 11. DYNAMIC EXECUTION INTERFACE (GET OR TRAIN)
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
    best_upgrade_sigma = UPGRADE_SIGMA_PER_POINT
    best_anchor_weight = GRID_ANCHOR_WEIGHT
    best_sprint_sigma = SPRINT_BOOST_SIGMA

    # Detect sprint weekend
    try:
        event_format = event.get_session_name(4)
        is_sprint = event_format == "Sprint"
    except Exception:
        is_sprint = False

    # Try loading cached model
    if os.path.exists(model_path):
        print(f"[f1_model] Loading cached model for {gp_clean} {year} from disk...")
        try:
            with open(model_path, "rb") as f:
                saved = pickle.load(f)
                model = saved["model"]
                final_cols = saved["final_cols"]
                available_features = saved["features"]
                best_upgrade_sigma = saved.get("best_upgrade_sigma", UPGRADE_SIGMA_PER_POINT)
                best_anchor_weight = saved.get("best_anchor_weight", GRID_ANCHOR_WEIGHT)
                best_sprint_sigma = saved.get("best_sprint_sigma", SPRINT_BOOST_SIGMA)
            update_progress("cached", f"Loaded cached model for {gp_clean}!", 100)
        except Exception as e:
            print(f"[f1_model] Failed to load cached model: {e}")

    # Build/inject form & team pace context even if cache is hot (uses results only - quick)
    update_progress("scheduling", "Analyzing F1 calendar schedule...", 10)
    training_races_2026 = discover_2026_races_before_target(gp_clean)
    historical_gp_races = []
    for offset, weight in [(1, 0.22), (2, 0.05)]:
        prev_year = year - offset
        try:
            prev_event = fastf1.get_event(prev_year, gp_clean)
            if prev_event and prev_event["RoundNumber"] > 0:
                historical_gp_races.append({
                    "year": prev_year,
                    "gp": prev_event["EventName"],
                    "weight": weight
                })
        except Exception:
            pass

    all_races = training_races_2026 + historical_gp_races
    
    # To keep dashboard queries extremely fast (<5 seconds) and avoid loading 46 full-season races,
    # we focus on prior same-season races and target same-GP historical races.
    pass

    if model is None:
        print(f"[f1_model] Re-training model dynamically for {gp_clean} {year}...")
        
        # Build training set features + labels
        race_cache = []
        N = len(all_races)
        for i, race in enumerate(all_races):
            percent = 15 + int((i / N) * 60)
            msg = f"Extracting features: {race['gp']} {race['year']} ({i+1}/{N})"
            update_progress("feature_engineering", msg, percent)
            
            features = build_race_features(race["year"], race["gp"], include_circuit_context=True)
            if features.empty:
                continue
            labels = get_race_labels(race["year"], race["gp"])
            if labels.empty:
                continue
            df = features.merge(labels, on="Driver", how="left").dropna(subset=["label"])
            df["label"] = df["label"].astype(int)
            df["sample_weight"] = race["weight"]
            df["is_2026"] = int(race["year"] == 2026)
            race_cache.append({
                "race": race,
                "df": df,
                "features": features,
                "labels": labels
            })

        if not race_cache:
            raise ValueError(f"No suitable training races identified for {gp_clean} {year}")

        # Inject teammate deltas
        for entry in race_cache:
            entry["df"] = add_teammate_deltas(entry["df"])
            entry["features"] = add_teammate_deltas(entry["features"])

        # Inject season form and team pace rankings chronologically
        races_2026_entries = [e for e in race_cache if e["race"]["year"] == 2026]
        cum_labels = []
        feat_sources = [e["features"] for e in races_2026_entries]
        
        for entry in races_2026_entries:
            if cum_labels:
                form = get_season_form(cum_labels)
                tpace = get_team_pace_rank(cum_labels, feat_sources)
                
                if not form.empty:
                    entry["df"] = entry["df"].merge(form, on="Driver", how="left")
                    entry["features"] = entry["features"].merge(form, on="Driver", how="left")
                    
                if not tpace.empty:
                    for target in [entry["df"], entry["features"]]:
                        target["_tnorm"] = target["Team"].replace(TEAM_NORM_MAP).fillna(target["Team"])
                        merged = target.merge(tpace, left_on="_tnorm", right_on="Team_norm", how="left")
                        target["team_2026_pace_rank"] = merged["team_2026_pace_rank"].values
                        target.drop(columns=["_tnorm", "Team_norm"], errors="ignore", inplace=True)
                        
            if not entry["labels"].empty:
                cum_labels.append(entry["labels"])

        df_train = pd.concat([e["df"] for e in race_cache], axis=0, ignore_index=True)
        available_features = [c for c in FEATURE_COLS if c in df_train.columns]
        
        # Parameter Calibration
        update_progress("calibration", "Grid-searching upgrade and adjustment parameters...", 80)
        if is_sprint:
            best_upgrade_sigma, best_sprint_sigma = calibrate_sigma(race_cache, available_features, gp_clean)
        else:
            best_upgrade_sigma, best_anchor_weight = calibrate_params(race_cache, available_features, gp_clean)

        # Print diagnostics
        print("\n=== RUNNING DIAGNOSTIC CV EVALUATIONS ===")
        evaluate_loo_cv(race_cache, available_features)
        ablation_study(race_cache, available_features)

        # Model training
        update_progress("training", "Fitting XGBoost pairwise ranking model...", 85)
        model, final_cols = train_model(df_train, available_features)
        
        # Cache to disk
        print(f"[f1_model] Saving trained model to {model_path}...")
        try:
            with open(model_path, "wb") as f:
                pickle.dump({
                    "model": model,
                    "final_cols": final_cols,
                    "features": available_features,
                    "best_upgrade_sigma": best_upgrade_sigma,
                    "best_anchor_weight": best_anchor_weight,
                    "best_sprint_sigma": best_sprint_sigma
                }, f)
        except Exception as e:
            print(f"[f1_model] Failed to cache model: {e}")

    # Build features for inference target GP
    update_progress("inference", f"Building features for {gp_clean} {year}...", 90)
    df_gp = build_race_features(year, gp_clean, include_circuit_context=True)
    if df_gp.empty:
        raise RuntimeError(f"Could not build features for inference target {gp_clean} {year}")

    df_gp = add_teammate_deltas(df_gp)

    # Resolve rolling season form & team pace rank from training labels (historical & same-season)
    with silent():
        prior_2026_labels = []
        prior_2026_feats = []
        
        # Check if we have race_cache in memory from dynamic training
        if 'race_cache' in locals() and race_cache:
            for entry in race_cache:
                if entry["race"]["year"] == 2026:
                    prior_2026_feats.append(entry["features"])
                    prior_2026_labels.append(entry["labels"])
        else:
            # Model loaded from pickle cache - bypass build_race_features for prior races!
            # Instead, load results directly and construct driver-team maps (under 0.1s per race)
            for race in training_races_2026:
                try:
                    session = fastf1.get_session(race["year"], race["gp"], "R")
                    session.load(telemetry=False, weather=False, messages=False)
                    res = session.results
                    if res is not None and not res.empty:
                        feat = pd.DataFrame({
                            "Driver": res["Abbreviation"],
                            "Team": res["TeamName"]
                        })
                        lbl = get_race_labels(race["year"], race["gp"])
                        if not feat.empty and not lbl.empty:
                            prior_2026_feats.append(feat)
                            prior_2026_labels.append(lbl)
                except Exception as e:
                    print(f"  ERROR loading fast-path results for {race['gp']} {race['year']}: {e}")
                    pass

        if prior_2026_labels:
            form = get_season_form(prior_2026_labels)
            if not form.empty:
                df_gp = df_gp.merge(form, on="Driver", how="left")
                
            tpace = get_team_pace_rank(prior_2026_labels, prior_2026_feats)
            if not tpace.empty:
                df_gp["_tnorm"] = df_gp["Team"].replace(TEAM_NORM_MAP).fillna(df_gp["Team"])
                df_gp = df_gp.merge(tpace, left_on="_tnorm", right_on="Team_norm", how="left")
                df_gp.drop(columns=["_tnorm", "Team_norm"], errors="ignore", inplace=True)

    # Run inference & post-prediction layers
    update_progress("inference", f"Running telemetry inference and adjustment layers...", 95)
    if available_features is None:
        available_features = [c for c in FEATURE_COLS if c in df_gp.columns]
    df_top = predict_top(model, final_cols, df_gp, available_features)
    
    df_adjusted = apply_upgrade_adjustment(df_top, gp_clean, upgrade_sigma=best_upgrade_sigma)
    if is_sprint:
        df_final = apply_sprint_adjustment(df_adjusted, year, gp_clean, sprint_sigma=best_sprint_sigma)
        score_col = "sprint_adjusted_score"
        pos_col = "sprint_adjusted_position"
    else:
        df_final = apply_grid_anchor(df_adjusted, year, gp_clean, anchor_weight=best_anchor_weight)
        score_col = "anchored_score"
        pos_col = "anchored_position"

    update_progress("complete", "Telemetry analysis finished!", 100)

    df_result = df_final[["Driver"]].copy()
    if "Team" in df_final.columns:
        df_result["Team"] = df_final["Team"].values
    if "grid_position" in df_final.columns:
        df_result["grid_position"] = df_final["grid_position"].values

    df_result["rank_score"] = df_final[score_col].values
    df_result = df_result.sort_values("rank_score", ascending=False).reset_index(drop=True)
    df_result["predicted_position"] = df_result.index + 1
    
    # Reset to idle
    update_progress("idle", "Ready", 0)
    
    return df_result


if __name__ == "__main__":
    print("Testing train_and_predict_for_race for Canada 2026...")
    res = train_and_predict_for_race(2026, "Canada")
    print("\nPrediction Results:")
    print(res.to_string(index=False))
