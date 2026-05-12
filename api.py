import os 
import math
import pickle
os.makedirs("./.f1_cache", exist_ok=True)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import fastf1
import pandas as pd

# Import the training and prediction functions from the model
from miami.miami_model import (
    build_full_training_set, build_race_features, train_model, predict_top,
    TRAINING_RACES_2026, HISTORICAL_MIAMI, FEATURE_COLS
)

app = FastAPI(title="F1 Oracle API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

fastf1.Cache.enable_cache("./.f1_cache")

# Cache the model to avoid retrain on every single page refresh
MODEL_CACHE = {"model": None, "final_cols": None, "features": None}
MODEL_FILE = "trained_model.pkl"

def get_or_train_model():
    if MODEL_CACHE["model"] is None:
        if os.path.exists(MODEL_FILE):
            print("Loading trained model from disk...")
            with open(MODEL_FILE, "rb") as f:
                saved = pickle.load(f)
                MODEL_CACHE["model"] = saved["model"]
                MODEL_CACHE["final_cols"] = saved["final_cols"]
                MODEL_CACHE["features"] = saved["features"]
            return MODEL_CACHE["model"], MODEL_CACHE["final_cols"], MODEL_CACHE["features"]
            
        print("Training model...")
        all_races = TRAINING_RACES_2026 + HISTORICAL_MIAMI
        df_train = build_full_training_set(all_races)
        
        # Filter to available features 
        available_features = [c for c in FEATURE_COLS if c in df_train.columns]
        
        model, final_cols = train_model(df_train, available_features)
        MODEL_CACHE["model"] = model
        MODEL_CACHE["final_cols"] = final_cols
        MODEL_CACHE["features"] = available_features
        
        print("Saving trained model to disk...")
        with open(MODEL_FILE, "wb") as f:
            pickle.dump({
                "model": model, 
                "final_cols": final_cols, 
                "features": available_features
            }, f)
        
    return MODEL_CACHE["model"], MODEL_CACHE["final_cols"], MODEL_CACHE["features"]

# In-memory cache for API endpoints to prevent slow fastf1 reloading
API_CACHE = {}

@app.get("/api/race/{year}/{gp}")
def get_race_dashboard(year: int, gp: str):
    cache_key = f"race_{year}_{gp}"
    if cache_key in API_CACHE:
        return API_CACHE[cache_key]

    try:
        
        model, final_cols, features = get_or_train_model()
        df_gp = build_race_features(year, gp)
        
        if df_gp.empty:
             raise HTTPException(status_code=404, detail="Race data not found in cache.")
             
        df_top = predict_top(model, final_cols, df_gp, features)
        
        # Convert prediction DataFrame to a dictionary for JSON
        predictions = df_top[["predicted_position", "Driver", "Team"]].to_dict(orient="records")

        # 2. GET ACTUAL RESULTS & LOGS
        session = fastf1.get_session(year, gp, 'R')
        session.load(telemetry=False, weather=False, messages=True)

        # Grab actual classification
        res = session.results
        actuals = []
        if not res.empty:
            df_actuals = pd.DataFrame({
                "actual_position": res["Position"],
                "Driver": res["Abbreviation"],
                "status": res["Status"],
                "points": res["Points"]
            })
            # Replace JSON-breaking NaN values with a dash
            df_actuals = df_actuals.fillna("-")
            actuals = df_actuals.to_dict(orient="records")

        # 3. GRAB RACE CONTROL LOGS
        logs = []
        if hasattr(session, 'race_control_messages') and not session.race_control_messages.empty:
            df_messages = session.race_control_messages.copy()
            interesting_categories = ['Flag', 'Penalty', 'SafetyCar', 'Drs']
            df_messages = df_messages[df_messages['Category'].isin(interesting_categories)]
            df_messages['Time'] = df_messages['Time'].astype(str).str.split('.').str[0]
            logs = df_messages[["Time", "Category", "Message"]].fillna("").to_dict(orient="records")

        response_data = {
            "race": f"{gp} {year}",
            "predictions": predictions,
            "actuals": actuals,
            "logs": logs
        }
        API_CACHE[cache_key] = response_data
        return response_data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/aero/{year}/{gp}")
def get_aero_setup(year: int, gp: str):
    cache_key = f"aero_{year}_{gp}"
    if cache_key in API_CACHE:
        return API_CACHE[cache_key]

    try:
        # Use Qualifying ('Q') for true, lowest-fuel ultimate setup
        session = fastf1.get_session(year, gp, 'Q')
        # Load telemetry to get the speed traces
        session.load(telemetry=True, weather=False, messages=False)
        
        aero_data = []
        for driver in session.results['Abbreviation']:
            try:
                lap = session.laps.pick_driver(driver).pick_fastest()
                if pd.isnull(lap['LapTime']):
                    continue
                
                # Extract the 10Hz telemetry for this specific lap
                tel = lap.get_telemetry()
                
                # FIX: Check if telemetry is empty or corrupted before doing math
                if tel.empty or 'Speed' not in tel.columns:
                    continue
                
                # Max speed is the proxy for Drag Efficiency (Straights)
                max_speed = float(tel['Speed'].max())
                s1_time = float(lap['Sector1Time'].total_seconds()) if pd.notnull(lap['Sector1Time']) else 0
                s3_time = float(lap['Sector3Time'].total_seconds()) if pd.notnull(lap['Sector3Time']) else 0
                
                if s3_time == 0 or math.isnan(max_speed) or math.isnan(s1_time):
                    print(f"Skipping {driver}: Speed data contains NaN or 0")
                    continue
                
                s1_s3_ratio = s1_time / s3_time

                aero_data.append({
                    "driver": driver,
                    "team": lap['Team'],
                    "max_speed": max_speed,
                    "s1_s3_ratio": s1_s3_ratio,
                    "s1_time": s1_time,
                    "s3_time": s3_time
                })
            except Exception as e:
                print(f"Skipping {driver} for aero map: {e}")
                
        response_data = {
            "race": f"{gp} {year}", 
            "aero_data": aero_data
        }
        API_CACHE[cache_key] = response_data
        return response_data
  
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/h2h/{year}/{gp}")
def get_h2h_data(year: int, gp: str):
    cache_key = f"h2h_{year}_{gp}"
    if cache_key in API_CACHE:
        return API_CACHE[cache_key]

    try:
        session = fastf1.get_session(year, gp, 'Q')
        session.load(telemetry=True, weather=False, messages=False)
        
        h2h_data = {}
        for driver in session.results['Abbreviation']:
            try:
                lap = session.laps.pick_driver(driver).pick_fastest()
                if pd.isnull(lap['LapTime']):
                    continue
                    
                tel = lap.get_telemetry()
                max_speed = float(tel['Speed'].max()) if not tel.empty and 'Speed' in tel.columns else 0
                s1_time = float(lap['Sector1Time'].total_seconds()) if pd.notnull(lap['Sector1Time']) else 0
                s3_time = float(lap['Sector3Time'].total_seconds()) if pd.notnull(lap['Sector3Time']) else 0
                lap_time = float(lap['LapTime'].total_seconds()) if pd.notnull(lap['LapTime']) else 0
                
                # Mock advanced metrics based on driver name length to keep it pseudo-random but consistent
                ers_mock = round(0.123 + (len(driver) * 0.031), 3)
                coast_mock = round(0.5 + (len(driver) * 0.12), 3)
                deg_mock = round(0.002 + (len(driver) * 0.001), 3)

                # Extract downsampled telemetry trace
                telemetry_trace = []
                if not tel.empty:
                    # Downsample to every 8th point to keep payload small but retain curve shape
                    tel_sampled = tel.iloc[::8]
                    for _, row in tel_sampled.iterrows():
                        telemetry_trace.append({
                            "distance": float(row["Distance"]) if pd.notnull(row.get("Distance")) else 0,
                            "speed": float(row["Speed"]) if pd.notnull(row.get("Speed")) else 0,
                            "throttle": float(row["Throttle"]) if pd.notnull(row.get("Throttle")) else 0,
                            "brake": float(row["Brake"]) if pd.notnull(row.get("Brake")) else 0,
                            "gear": int(row["nGear"]) if pd.notnull(row.get("nGear")) else 0,
                        })

                h2h_data[driver] = {
                    "lap_time": lap_time,
                    "s1_time": s1_time,
                    "s3_time": s3_time,
                    "top_speed": max_speed,
                    "s1_s3_ratio": s1_time / s3_time if s3_time > 0 else 0,
                    "ers_efficiency": ers_mock,
                    "lift_and_coast": coast_mock,
                    "stint_deg_rate": deg_mock,
                    "telemetry": telemetry_trace
                }
            except Exception as e:
                print(f"Skipping {driver} for H2H: {e}")
                
        response_data = {"h2h_data": h2h_data}
        API_CACHE[cache_key] = response_data
        return response_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))