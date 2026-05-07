import fastf1
import warnings
warnings.filterwarnings("ignore")
fastf1.set_log_level("WARNING")
fastf1.Cache.enable_cache("/Users/dhurtado/f1/f1_cache")

session = fastf1.get_session(2026, 1, "R") # First race of 2026
session.load(telemetry=False, weather=False, messages=False)
teams = session.results['TeamName'].unique()
for t in teams:
    print(t)
