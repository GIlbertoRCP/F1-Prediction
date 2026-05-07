import importlib.util
import os
import sys

# ── Dynamic import of f1_fe ────────────────────────────────────────────────────
_spec = importlib.util.spec_from_file_location(
    "f1_fe",
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "f1-api", "f1_fe.py")
    ),
)
f1_fe = importlib.util.module_from_spec(_spec)
sys.modules["fe"] = f1_fe
_spec.loader.exec_module(f1_fe)

if __name__ == "__main__":
    YEAR = 2026
    GP = "Miami"
    TARGET_SESSION = "FP1"

    print("=========================================")
    print(f"   GENERAL METRICS - {TARGET_SESSION}    ")
    print("=========================================")

    df_best = f1_fe.get_best_lap_delta(YEAR, GP, TARGET_SESSION)
    print(f"\n{TARGET_SESSION} Best Lap Delta:")
    print(df_best.to_string(index=False))

    df_clean = f1_fe.get_clean_laps_count(YEAR, GP, TARGET_SESSION)
    print(f"\n{TARGET_SESSION} Clean Laps Count:")
    print(df_clean.to_string(index=False))

    df_sectors = f1_fe.get_sector_deltas(YEAR, GP, TARGET_SESSION)
    print(f"\n{TARGET_SESSION} Sector Deltas:")
    print(df_sectors.to_string(index=False))

    df_speed = f1_fe.get_max_speed_trap(YEAR, GP, TARGET_SESSION)
    print(f"\n{TARGET_SESSION} Max Speed Trap:")
    print(df_speed.to_string(index=False))

    df_pu = f1_fe.get_pu_deployment_asymmetry(YEAR, GP, TARGET_SESSION)
    print(f"\n{TARGET_SESSION} S1 vs S3 Ratio (PU Deployment Asymmetry):")
    print(df_pu.to_string(index=False))

    df_ers = f1_fe.get_ers_efficiency_proxy(YEAR, GP, TARGET_SESSION)
    print(f"\n{TARGET_SESSION} ERS Efficiency Proxy (Delta vs Field):")
    print(df_ers.to_string(index=False))

    df_evo = f1_fe.get_track_evolution(YEAR, GP, TARGET_SESSION)
    print(f"\n{TARGET_SESSION} Global Track Evolution (Seconds):")
    print(df_evo.head(5).to_string(index=False))

    print("\n=========================================")
    print(f"   COMPOUND SPECIFIC METRICS - {TARGET_SESSION} ")
    print("=========================================")

    compounds = ["SOFT", "MEDIUM", "HARD"]

    for comp in compounds:
        print(f"\n--- COMPOUND: {comp} ---")
        try:
            df_laps = f1_fe.get_laps_on_compound(YEAR, GP, TARGET_SESSION, compound=comp)
            if df_laps is not None and not df_laps.empty:
                print(f"Laps on {comp}:")
                print(df_laps.to_string(index=False))
                
                df_avg = f1_fe.get_compound_avg(YEAR, GP, TARGET_SESSION, compound=comp)
                print(f"Avg Pace on {comp}:")
                print(df_avg.to_string(index=False))
            else:
                print(f"No laps recorded on {comp}.")
        except Exception:
            print(f"No laps recorded on {comp}.")

    print("\n=========================================")
    print(f"   LONG RUN METRICS (>=5 Laps) - {TARGET_SESSION} ")
    print("=========================================")

    try:
        df_longrun_vg = f1_fe.get_longrun_avg_pace(YEAR, GP, TARGET_SESSION)
        print(f"\n{TARGET_SESSION} Long Run Avg Pace (Overall):")
        print(df_longrun_vg)
    except Exception:
        pass

    try:
        df_compound = f1_fe.get_longrun_compound(YEAR, GP, TARGET_SESSION, min_laps=5)
        print(f"\n{TARGET_SESSION} Long Run Primary Compound:")
        print(df_compound.to_string(index=False))
    except Exception:
        pass

    try:
        df_lc = f1_fe.get_lift_and_coast_laps(YEAR, GP, TARGET_SESSION, min_laps=5)
        print(f"\n{TARGET_SESSION} Average Lift & Coast Time per Lap (Seconds):")
        print(df_lc.to_string(index=False))
    except Exception:
        pass

    try:
        df_speed_var = f1_fe.get_speed_trap_variance(YEAR, GP, TARGET_SESSION, min_laps=5)
        print(f"\n{TARGET_SESSION} Speed Trap Variance (km/h) during Long Runs:")
        print(df_speed_var.to_string(index=False))
    except Exception:
        pass

    for comp in compounds:
        print(f"\n--- LONG RUNS ON {comp} ---")
        try:
            df_longrun_deg_rate = f1_fe.get_longrun_deg_rate(YEAR, GP, TARGET_SESSION, compound=comp)
            if df_longrun_deg_rate is not None and len(df_longrun_deg_rate) > 0:
                print(f"Degradation Rate:")
                print(df_longrun_deg_rate)
                
                df_consistency = f1_fe.get_longrun_consistency(YEAR, GP, TARGET_SESSION, compound=comp, min_laps=5)
                print(f"Consistency (Std Dev):")
                print(df_consistency.to_string(index=False))
                
                df_fuel_pace = f1_fe.get_fuel_corrected_pace(YEAR, GP, TARGET_SESSION, compound=comp, window_size=5)
                print(f"Fuel Corrected Base Pace:")
                print(df_fuel_pace.to_string(index=False))
                
                df_deg_total = f1_fe.get_longrun_deg_total(YEAR, GP, TARGET_SESSION, compound=comp, min_laps=5, expected_stint_length=18)
                print(f"Total Degradation Projection (18 laps):")
                print(df_deg_total.to_string(index=False))
            else:
                print(f"Not enough long run data for {comp}.")
        except Exception:
            print(f"Not enough long run data for {comp}.")
