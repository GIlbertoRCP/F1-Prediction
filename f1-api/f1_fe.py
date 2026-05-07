import fastf1
import pandas as pd
import numpy as np

fastf1.Cache.enable_cache('./f1_cache')

# CIRCUITO
def get_best_lap_delta(year: int, gp: str, session_type: str) -> pd.DataFrame:
    """
    Calculates best_lap_delta for all drivers dynamically based on session_type:
    (driver_best_laptime - field_best_laptime) / field_best_laptime
    
    Only considers clean flying laps without traffic or yellow flags.
    """
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=False, weather=False, messages=False)
    
    prefix = session_type.lower()
    laps = session.laps.copy()

    # Quality filters
    laps = laps[
        (laps['TrackStatus'] == '1')
        & (laps['PitOutTime'].isna())
        & (laps['PitInTime'].isna())
        & (laps['LapTime'].notna())
        & (laps['LapTime'] > pd.Timedelta(0))
    ]

    # Best lap per driver
    driver_best = (
        laps.groupby('Driver')['LapTime']
        .min()
        .reset_index()
        .rename(columns={'LapTime': 'driver_best_laptime'})
    )

    # Field reference lap
    field_best = driver_best['driver_best_laptime'].min()

    # Relative Delta
    driver_best['field_best_laptime'] = field_best
    driver_best[f'{prefix}_best_lap_delta'] = (
        (driver_best['driver_best_laptime'] - field_best).dt.total_seconds() 
        / field_best.total_seconds()
    )

    # Convert times to seconds for ML models
    driver_best[f'{prefix}_driver_best_laptime_s'] = driver_best['driver_best_laptime'].dt.total_seconds()
    driver_best[f'{prefix}_field_best_laptime_s'] = field_best.total_seconds()

    return driver_best[['Driver', f'{prefix}_driver_best_laptime_s', 
                         f'{prefix}_field_best_laptime_s', f'{prefix}_best_lap_delta']]

def get_clean_laps_count(year: int, gp: str, session_type: str) -> pd.DataFrame:
    """
    Counts clean laps per driver in the specified session.
    Filters out aborted laps using the 107% rule threshold.
    """
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=False, weather=False, messages=False)
    
    prefix = session_type.lower()
    laps = session.laps.copy()

    best_time = laps['LapTime'].min()
    max_acceptable = best_time * 1.07

    clean_laps = laps[
        (laps['TrackStatus'] == '1')
        & (laps['PitOutTime'].isna())
        & (laps['PitInTime'].isna())
        & (laps['LapTime'].notna())
        & (laps['LapTime'] > pd.Timedelta(0))
        & (laps['LapTime'] <= max_acceptable)
    ]

    result = clean_laps.groupby('Driver').size().reset_index(name=f'{prefix}_clean_laps_count')

    # Include drivers with 0 clean laps
    all_drivers = session.laps['Driver'].unique()
    result = (
        pd.DataFrame({'Driver': all_drivers})
        .merge(result, on='Driver', how='left')
        .fillna({f'{prefix}_clean_laps_count': 0})
    )
    result[f'{prefix}_clean_laps_count'] = result[f'{prefix}_clean_laps_count'].astype(int)

    return result.sort_values(f'{prefix}_clean_laps_count', ascending=False)

def get_compound_avg(year: int, gp: str, session_type: str, compound: str = 'HARD') -> pd.DataFrame:
    """
    Average lap time on a specific compound, normalized by tyre life 
    to correct for degradation evolution. Requires at least 3 clean laps.
    """
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=False, weather=False, messages=False)
    
    prefix = session_type.lower()
    comp_lower = compound.lower()
    laps = session.laps.copy()

    best_time = laps['LapTime'].min()
    max_acceptable = best_time * 1.07

    target_laps = laps[
        (laps['Compound'] == compound.upper())
        & (laps['TrackStatus'] == '1')
        & (laps['PitOutTime'].isna())
        & (laps['PitInTime'].isna())
        & (laps['LapTime'].notna())
        & (laps['LapTime'] > pd.Timedelta(0))
        & (laps['LapTime'] <= max_acceptable)
    ].copy()

    target_laps['LapTime_s'] = target_laps['LapTime'].dt.total_seconds()

    # Normalize by tyre life (generic degradation correction)
    DEG_CORRECTION = 0.08 
    target_laps['LapTime_corrected'] = target_laps['LapTime_s'] - (target_laps['TyreLife'] * DEG_CORRECTION)

    # Filter drivers with at least 3 valid laps
    counts = target_laps.groupby('Driver')['LapTime_s'].count()
    valid_drivers = counts[counts >= 3].index
    target_laps = target_laps[target_laps['Driver'].isin(valid_drivers)]

    result = (
        target_laps.groupby('Driver')
        .agg(
            avg=('LapTime_corrected', 'mean'),
            laps_count=('LapTime_s', 'count'),
            best=('LapTime_s', 'min')
        )
        .rename(columns={
            'avg': f'{prefix}_compound_{comp_lower}_avg',
            'laps_count': f'{prefix}_compound_{comp_lower}_laps',
            'best': f'{prefix}_compound_{comp_lower}_best'
        })
        .reset_index()
    )

    all_drivers = session.laps['Driver'].unique()
    result = pd.DataFrame({'Driver': all_drivers}).merge(result, on='Driver', how='left')

    return result.sort_values(f'{prefix}_compound_{comp_lower}_avg')

def get_sector_deltas(year: int, gp: str, session_type: str) -> pd.DataFrame:
    """
    Calculates sector deltas for S1, S2, and S3 simultaneously to avoid
    loading the session data multiple times.
    """
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=False, weather=False, messages=False)
    
    prefix = session_type.lower()
    laps = session.laps.copy()

    best_lap_time = laps['LapTime'].min()
    max_acceptable_lap = best_lap_time * 1.07

    valid_laps = laps[
        (laps['TrackStatus'] == '1')
        & (laps['PitOutTime'].isna())
        & (laps['PitInTime'].isna())
        & (laps['LapTime'].notna())
        & (laps['LapTime'] <= max_acceptable_lap)
    ].copy()

    # Convert Timedeltas to seconds safely
    for sec in [1, 2, 3]:
        valid_laps[f'S{sec}_s'] = valid_laps[f'Sector{sec}Time'].dt.total_seconds()

    # Aggregate times
    driver_stats = valid_laps.groupby('Driver').agg(
        s1_avg=('S1_s', 'mean'), s1_best=('S1_s', 'min'),
        s2_avg=('S2_s', 'mean'), s2_best=('S2_s', 'min'),
        s3_avg=('S3_s', 'mean'), s3_best=('S3_s', 'min')
    ).reset_index()

    # Calculate global deltas per sector
    for sec in [1, 2, 3]:
        best_sec = driver_stats[f's{sec}_best'].min()
        driver_stats[f'{prefix}_sector{sec}_delta'] = driver_stats[f's{sec}_avg'] - best_sec

    # Filter columns to return
    cols_to_keep = ['Driver', f'{prefix}_sector1_delta', f'{prefix}_sector2_delta', f'{prefix}_sector3_delta']
    driver_stats = driver_stats[cols_to_keep]

    all_drivers = session.laps['Driver'].unique()
    result = pd.DataFrame({'Driver': all_drivers}).merge(driver_stats, on='Driver', how='left')

    return result.sort_values(f'{prefix}_sector1_delta').reset_index(drop=True)

def get_max_speed_trap(year: int, gp: str, session_type: str) -> pd.DataFrame:
    """
    Extracts the highest speed trap (SpeedST) value recorded by each driver 
    in km/h during representative laps.
    """
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=False, weather=False, messages=False)
    
    prefix = session_type.lower()
    laps = session.laps.copy()

    best_lap_time = laps['LapTime'].min()
    max_acceptable_lap = best_lap_time * 1.07

    valid_laps = laps[
        (laps['TrackStatus'] == '1')
        & (laps['PitOutTime'].isna())
        & (laps['PitInTime'].isna())
        & (laps['SpeedST'].notna())
        & (laps['SpeedST'] > 0)
        & (laps['LapTime'].notna())
        & (laps['LapTime'] <= max_acceptable_lap)
    ].copy()

    driver_stats = valid_laps.groupby('Driver').agg(
        max_speed=('SpeedST', 'max'),
        avg_speed=('SpeedST', 'mean'),
        count=('SpeedST', 'count')
    ).rename(columns={
        'max_speed': f'{prefix}_max_speed_trap',
        'avg_speed': f'{prefix}_speed_trap_avg',
        'count': f'{prefix}_valid_laps_count'
    }).reset_index()

    absolute_max = driver_stats[f'{prefix}_max_speed_trap'].max()
    driver_stats[f'{prefix}_speed_trap_delta'] = absolute_max - driver_stats[f'{prefix}_max_speed_trap']

    all_drivers = session.laps['Driver'].unique()
    result = pd.DataFrame({'Driver': all_drivers}).merge(driver_stats, on='Driver', how='left')

    return result.sort_values(f'{prefix}_speed_trap_delta').reset_index(drop=True)

def get_laps_on_compound(year: int, gp: str, session_type: str, compound: str = 'HARD') -> pd.DataFrame:
    """
    Calculates the total number of completed laps by each driver 
    using a specific compound during the session.
    """
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=False, weather=False, messages=False)
    
    prefix = session_type.lower()
    comp_lower = compound.lower()
    laps = session.laps.copy()

    target_laps = laps[
        (laps['Compound'] == compound.upper())
        & (laps['LapTime'].notna())
    ].copy()

    driver_stats = target_laps.groupby('Driver').agg(
        laps_count=('LapTime', 'count')
    ).rename(columns={
        'laps_count': f'{prefix}_laps_on_{comp_lower}'
    }).reset_index()

    all_drivers = session.laps['Driver'].unique()
    result = (
        pd.DataFrame({'Driver': all_drivers})
        .merge(driver_stats, on='Driver', how='left')
        .fillna({f'{prefix}_laps_on_{comp_lower}': 0})
    )

    result[f'{prefix}_laps_on_{comp_lower}'] = result[f'{prefix}_laps_on_{comp_lower}'].astype(int)

    return result.sort_values(f'{prefix}_laps_on_{comp_lower}', ascending=False).reset_index(drop=True)

# LONG RUN
def get_longrun_avg_pace(year: int, gp: str, session_type: str, compound: str = 'MEDIUM', window_size: int = 8) -> pd.DataFrame:
    """
    Calculates the normalized average pace of the best N strictly consecutive laps 
    on a specific compound (Long Run Race Pace).
    
    Includes dynamic tire degradation correction, strict validation, and 
    empty-state handling for sessions where long runs do not occur.
    """
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=False, weather=False, messages=False)
    
    prefix = session_type.lower()
    comp_lower = compound.lower()
    col_name = f'{prefix}_longrun_{comp_lower}_avg_pace'
    
    laps = session.laps.copy()
    all_drivers = laps['Driver'].unique()

    # Calculate 107% rule threshold based on the overall best lap time
    best_lap_time = laps['LapTime'].min()
    max_acceptable_lap = best_lap_time * 1.07

    # Apply quality filters for clean laps
    valid_laps = laps[
        (laps['Compound'] == compound.upper())
        & (laps['TrackStatus'] == '1')
        & (laps['PitOutTime'].isna())
        & (laps['PitInTime'].isna())
        & (laps['LapTime'].notna())
        & (laps['LapTime'] > pd.Timedelta(0))
        & (laps['LapTime'] <= max_acceptable_lap)
    ].copy()

    # DEFENSIVE CHECK: If no laps meet the criteria (e.g., Qualifying session), 
    # short-circuit and return NaNs to prevent pandas apply() crashes on empty DataFrames.
    if valid_laps.empty:
        result = pd.DataFrame({'Driver': all_drivers})
        result[col_name] = np.nan
        return result

    # Convert Timedeltas to seconds
    valid_laps['LapTime_s'] = valid_laps['LapTime'].dt.total_seconds()

    # Dynamic Tyre Degradation Correction
    if compound.upper() == 'SOFT':
        deg_correction = 0.12
    elif compound.upper() == 'HARD':
        deg_correction = 0.05
    else:
        deg_correction = 0.08 

    # Normalize lap times
    valid_laps['LapTime_corrected'] = valid_laps['LapTime_s'] - (valid_laps['TyreLife'] * deg_correction)

    # Sort strictly
    valid_laps = valid_laps.sort_values(by=['Driver', 'Stint', 'LapNumber'])

    def get_best_consecutive_window(df: pd.DataFrame, window: int) -> pd.Series:
        if len(df) < window:
            return pd.Series({col_name: np.nan})
            
        rolling_avg = df['LapTime_corrected'].rolling(window=window).mean()
        
        rolling_lap_max = df['LapNumber'].rolling(window=window).max()
        rolling_lap_min = df['LapNumber'].rolling(window=window).min()
        is_strictly_consecutive = (rolling_lap_max - rolling_lap_min) == (window - 1)
        
        valid_windows = rolling_avg[is_strictly_consecutive]
        
        if valid_windows.empty:
            return pd.Series({col_name: np.nan})
            
        return pd.Series({col_name: valid_windows.min()})

    stint_stats = (
        valid_laps.groupby(['Driver', 'Stint'])
        .apply(get_best_consecutive_window, window=window_size, include_groups=False)
        .reset_index()
    )

    # Edge-case fallback: if Pandas still stripped the column somehow
    if col_name not in stint_stats.columns:
        stint_stats[col_name] = np.nan

    driver_stats = (
        stint_stats.groupby('Driver')
        .agg({col_name: 'min'})
        .reset_index()
    )

    result = (
        pd.DataFrame({'Driver': all_drivers})
        .merge(driver_stats, on='Driver', how='left')
    )

    return result.sort_values(col_name).reset_index(drop=True)

def get_longrun_deg_rate(year: int, gp: str, session_type: str, compound: str = 'MEDIUM', min_laps: int = 5) -> pd.DataFrame:
    """
    Calculates the tire degradation rate (slope of linear regression) 
    in seconds per lap during a long run stint.
    
    A positive slope indicates net degradation (lap times getting slower).
    A negative slope indicates fuel burn outpaces tire wear (lap times getting faster).
    """
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=False, weather=False, messages=False)
    
    prefix = session_type.lower()
    comp_lower = compound.lower()
    col_name = f'{prefix}_longrun_{comp_lower}_deg_rate'
    
    laps = session.laps.copy()
    all_drivers = laps['Driver'].unique()

    # Calculate 107% rule threshold to filter out heavily aborted laps
    best_lap_time = laps['LapTime'].min()
    max_acceptable_lap = best_lap_time * 1.07

    # Apply quality filters
    valid_laps = laps[
        (laps['Compound'] == compound.upper())
        & (laps['TrackStatus'] == '1')
        & (laps['PitOutTime'].isna())
        & (laps['PitInTime'].isna())
        & (laps['LapTime'].notna())
        & (laps['LapTime'] > pd.Timedelta(0))
        & (laps['LapTime'] <= max_acceptable_lap)
    ].copy()

    # DEFENSIVE CHECK: Short-circuit if session has no valid data (e.g., Qualifying)
    if valid_laps.empty:
        result = pd.DataFrame({'Driver': all_drivers})
        result[col_name] = np.nan
        return result

    # Convert Timedeltas to seconds
    valid_laps['LapTime_s'] = valid_laps['LapTime'].dt.total_seconds()
    valid_laps = valid_laps.sort_values(by=['Driver', 'Stint', 'LapNumber'])

    def calculate_deg_slope(df: pd.DataFrame) -> pd.Series:
        # Require a minimum number of valid laps to establish a reliable trend
        if len(df) < min_laps:
            return pd.Series({col_name: np.nan, 'laps_in_stint': len(df)})
            
        # x: Tire age (number of laps old)
        # y: Lap time in seconds
        x = df['TyreLife'].values
        y = df['LapTime_s'].values
        
        # Calculate linear regression (degree 1 polynomial)
        # polyfit returns [slope, intercept]
        slope, _ = np.polyfit(x, y, 1)
        
        return pd.Series({col_name: slope, 'laps_in_stint': len(df)})

    # Apply the slope calculation per stint
    stint_stats = (
        valid_laps.groupby(['Driver', 'Stint'])
        .apply(calculate_deg_slope, include_groups=False)
        .reset_index()
    )

    # Edge-case fallback
    if col_name not in stint_stats.columns:
        stint_stats[col_name] = np.nan
        stint_stats['laps_in_stint'] = 0

    # Filter out invalid stints (those that returned NaN slope)
    valid_stints = stint_stats.dropna(subset=[col_name])

    # If no stints passed the min_laps threshold, return NaNs
    if valid_stints.empty:
        result = pd.DataFrame({'Driver': all_drivers})
        result[col_name] = np.nan
        return result

    # If a driver did multiple long runs, select the one with the most laps 
    # to get the most statistically significant degradation rate
    best_stints = (
        valid_stints.sort_values(['Driver', 'laps_in_stint'], ascending=[True, False])
        .drop_duplicates('Driver')
    )

    driver_stats = best_stints[['Driver', col_name]]

    # Reintegrate all drivers
    result = (
        pd.DataFrame({'Driver': all_drivers})
        .merge(driver_stats, on='Driver', how='left')
    )

    # Sort from best degradation (lowest slope) to worst (highest slope)
    return result.sort_values(col_name).reset_index(drop=True)

def get_longrun_deg_total(year: int, gp: str, session_type: str, compound: str = 'MEDIUM', min_laps: int = 5, expected_stint_length: int = 15) -> pd.DataFrame:
    """
    Calculates the estimated total time loss (in seconds) over a projected full stint.
    Formula: Degradation Rate (slope) * Expected Stint Length.
    
    This translates raw degradation per lap into a strategic variable for 
    pit-window calculations and undercut vulnerability models.
    """
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=False, weather=False, messages=False)
    
    prefix = session_type.lower()
    comp_lower = compound.lower()
    col_rate = f'{prefix}_longrun_{comp_lower}_deg_rate'
    col_total = f'{prefix}_longrun_{comp_lower}_deg_total'
    
    laps = session.laps.copy()
    all_drivers = laps['Driver'].unique()

    # Calculate 107% rule threshold
    best_lap_time = laps['LapTime'].min()
    max_acceptable_lap = best_lap_time * 1.07

    # Apply quality filters
    valid_laps = laps[
        (laps['Compound'] == compound.upper())
        & (laps['TrackStatus'] == '1')
        & (laps['PitOutTime'].isna())
        & (laps['PitInTime'].isna())
        & (laps['LapTime'].notna())
        & (laps['LapTime'] > pd.Timedelta(0))
        & (laps['LapTime'] <= max_acceptable_lap)
    ].copy()

    # DEFENSIVE CHECK: Short-circuit if session has no valid data
    if valid_laps.empty:
        result = pd.DataFrame({'Driver': all_drivers})
        result[col_rate] = np.nan
        result[col_total] = np.nan
        return result

    valid_laps['LapTime_s'] = valid_laps['LapTime'].dt.total_seconds()
    valid_laps = valid_laps.sort_values(by=['Driver', 'Stint', 'LapNumber'])

    def calculate_deg_metrics(df: pd.DataFrame) -> pd.Series:
        if len(df) < min_laps:
            return pd.Series({
                col_rate: np.nan, 
                col_total: np.nan, 
                'laps_in_stint': len(df)
            })
            
        x = df['TyreLife'].values
        y = df['LapTime_s'].values
        
        # Calculate linear regression slope (seconds per lap)
        slope, _ = np.polyfit(x, y, 1)
        
        # Extrapolate to the expected stint length
        deg_total = slope * expected_stint_length
        
        return pd.Series({
            col_rate: slope, 
            col_total: deg_total, 
            'laps_in_stint': len(df)
        })

    # Apply calculations per stint
    stint_stats = (
        valid_laps.groupby(['Driver', 'Stint'])
        .apply(calculate_deg_metrics, include_groups=False)
        .reset_index()
    )

    # Edge-case fallback
    if col_total not in stint_stats.columns:
        stint_stats[col_rate] = np.nan
        stint_stats[col_total] = np.nan
        stint_stats['laps_in_stint'] = 0

    valid_stints = stint_stats.dropna(subset=[col_total])

    if valid_stints.empty:
        result = pd.DataFrame({'Driver': all_drivers})
        result[col_rate] = np.nan
        result[col_total] = np.nan
        return result

    # Select the most reliable stint (the one with the most laps)
    best_stints = (
        valid_stints.sort_values(['Driver', 'laps_in_stint'], ascending=[True, False])
        .drop_duplicates('Driver')
    )

    driver_stats = best_stints[['Driver', col_rate, col_total]]

    # Reintegrate all drivers
    result = (
        pd.DataFrame({'Driver': all_drivers})
        .merge(driver_stats, on='Driver', how='left')
    )

    # Sort from least total time lost to most
    return result.sort_values(col_total).reset_index(drop=True)

def get_longrun_consistency(year: int, gp: str, session_type: str, compound: str = 'MEDIUM', min_laps: int = 5) -> pd.DataFrame:
    """
    Calculates the long run consistency (Standard Deviation) of a driver 
    during a stint. 
    
    A lower value indicates a highly consistent driver (metronome). 
    A higher value indicates erratic driving, mistakes, or dealing with traffic.
    Applies tire degradation correction to isolate driver consistency 
    from natural tire wear and fuel burn.
    """
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=False, weather=False, messages=False)
    
    prefix = session_type.lower()
    comp_lower = compound.lower()
    col_name = f'{prefix}_longrun_{comp_lower}_consistency'
    
    laps = session.laps.copy()
    all_drivers = laps['Driver'].unique()

    # Calculate 107% rule threshold
    best_lap_time = laps['LapTime'].min()
    max_acceptable_lap = best_lap_time * 1.07

    # Apply quality filters
    valid_laps = laps[
        (laps['Compound'] == compound.upper())
        & (laps['TrackStatus'] == '1')
        & (laps['PitOutTime'].isna())
        & (laps['PitInTime'].isna())
        & (laps['LapTime'].notna())
        & (laps['LapTime'] > pd.Timedelta(0))
        & (laps['LapTime'] <= max_acceptable_lap)
    ].copy()

    # DEFENSIVE CHECK: Short-circuit if session has no valid data
    if valid_laps.empty:
        result = pd.DataFrame({'Driver': all_drivers})
        result[col_name] = np.nan
        return result

    # Convert Timedeltas to seconds
    valid_laps['LapTime_s'] = valid_laps['LapTime'].dt.total_seconds()

    # Dynamic Tyre Degradation Correction to detrend the data
    if compound.upper() == 'SOFT':
        deg_correction = 0.12
    elif compound.upper() == 'HARD':
        deg_correction = 0.05
    else:
        deg_correction = 0.08 

    valid_laps['LapTime_corrected'] = valid_laps['LapTime_s'] - (valid_laps['TyreLife'] * deg_correction)
    valid_laps = valid_laps.sort_values(by=['Driver', 'Stint', 'LapNumber'])

    def calculate_std_dev(df: pd.DataFrame) -> pd.Series:
        # Require a minimum number of valid laps for statistical significance
        if len(df) < min_laps:
            return pd.Series({col_name: np.nan, 'laps_in_stint': len(df)})
            
        # Calculate the sample standard deviation (ddof=1 is default in Pandas)
        # of the detrended lap times.
        consistency = df['LapTime_corrected'].std()
        
        return pd.Series({col_name: consistency, 'laps_in_stint': len(df)})

    # Apply calculations per stint
    stint_stats = (
        valid_laps.groupby(['Driver', 'Stint'])
        .apply(calculate_std_dev, include_groups=False)
        .reset_index()
    )

    # Edge-case fallback
    if col_name not in stint_stats.columns:
        stint_stats[col_name] = np.nan
        stint_stats['laps_in_stint'] = 0

    valid_stints = stint_stats.dropna(subset=[col_name])

    if valid_stints.empty:
        result = pd.DataFrame({'Driver': all_drivers})
        result[col_name] = np.nan
        return result

    # Select the stint with the most laps. If tied, pick the one where the driver 
    # was most consistent (lowest standard deviation).
    best_stints = (
        valid_stints.sort_values(['Driver', 'laps_in_stint', col_name], ascending=[True, False, True])
        .drop_duplicates('Driver')
    )

    driver_stats = best_stints[['Driver', col_name]]

    # Reintegrate all drivers
    result = (
        pd.DataFrame({'Driver': all_drivers})
        .merge(driver_stats, on='Driver', how='left')
    )

    # Sort from most consistent (lowest standard deviation) to most erratic
    return result.sort_values(col_name).reset_index(drop=True)

def get_longrun_compound(year: int, gp: str, session_type: str, min_laps: int = 5) -> pd.DataFrame:
    """
    Identifies the tire compound used by each driver for their primary long run stint.
    
    If a driver completed multiple long runs, it selects the compound from 
    the stint with the highest number of valid consecutive laps.
    Outputs a categorical variable (e.g., 'SOFT', 'MEDIUM', 'HARD') for ML normalization.
    """
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=False, weather=False, messages=False)
    
    prefix = session_type.lower()
    col_compound = f'{prefix}_longrun_compound'
    col_laps = f'{prefix}_longrun_stint_laps'
    
    laps = session.laps.copy()
    all_drivers = laps['Driver'].unique()

    # Calculate 107% rule threshold
    best_lap_time = laps['LapTime'].min()
    max_acceptable_lap = best_lap_time * 1.07

    # Apply quality filters to count only representative laps
    valid_laps = laps[
        (laps['TrackStatus'] == '1')
        & (laps['PitOutTime'].isna())
        & (laps['PitInTime'].isna())
        & (laps['LapTime'].notna())
        & (laps['LapTime'] > pd.Timedelta(0))
        & (laps['LapTime'] <= max_acceptable_lap)
        & (laps['Compound'].notna())  # Ensure compound data is logged
    ].copy()

    # DEFENSIVE CHECK: Short-circuit if session has no valid data (e.g., Qualifying)
    if valid_laps.empty:
        result = pd.DataFrame({'Driver': all_drivers})
        result[col_compound] = np.nan
        result[col_laps] = 0
        return result

    # Group by Driver, Stint, and Compound to count valid laps per stint
    stint_stats = (
        valid_laps.groupby(['Driver', 'Stint', 'Compound'])
        .agg(laps_in_stint=('LapTime', 'count'))
        .reset_index()
    )

    # Filter out short runs (e.g., scrubbed tires, qualy sims)
    valid_stints = stint_stats[stint_stats['laps_in_stint'] >= min_laps].copy()

    # If no stints passed the minimum laps threshold
    if valid_stints.empty:
        result = pd.DataFrame({'Driver': all_drivers})
        result[col_compound] = np.nan
        result[col_laps] = 0
        return result

    # Sort to prioritize the stint with the maximum number of laps per driver
    # drop_duplicates keeps only the top row (longest stint) for each driver
    best_stints = (
        valid_stints.sort_values(['Driver', 'laps_in_stint'], ascending=[True, False])
        .drop_duplicates('Driver')
    )

    # Rename columns for the final dataset
    driver_stats = best_stints[['Driver', 'Compound', 'laps_in_stint']].rename(
        columns={
            'Compound': col_compound,
            'laps_in_stint': col_laps
        }
    )

    # Reintegrate all drivers, leaving NaN for those without a long run
    result = (
        pd.DataFrame({'Driver': all_drivers})
        .merge(driver_stats, on='Driver', how='left')
        .fillna({col_laps: 0})
    )
    
    result[col_laps] = result[col_laps].astype(int)

    # Sort from longest stint to shortest
    return result.sort_values(col_laps, ascending=False).reset_index(drop=True)

def get_fuel_corrected_pace(year: int, gp: str, session_type: str, compound: str = 'MEDIUM', window_size: int = 5) -> pd.DataFrame:
    """
    Calculates the 'True Base Pace' by correcting lap times for both 
    dynamic tire degradation and estimated fuel loads.
    
    Fuel load is estimated dynamically based on the total length of the stint.
    Allows fair pace comparison between drivers running different fuel programs.
    """
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=False, weather=False, messages=False)
    
    prefix = session_type.lower()
    comp_lower = compound.lower()
    
    col_pace = f'{prefix}_{comp_lower}_fuel_corrected_pace'
    col_est_fuel = f'{prefix}_{comp_lower}_est_start_fuel_kg'
    
    laps = session.laps.copy()
    all_drivers = laps['Driver'].unique()

    # 107% rule threshold
    best_lap_time = laps['LapTime'].min()
    max_acceptable_lap = best_lap_time * 1.07

    # Quality filters
    valid_laps = laps[
        (laps['Compound'] == compound.upper())
        & (laps['TrackStatus'] == '1')
        & (laps['PitOutTime'].isna())
        & (laps['PitInTime'].isna())
        & (laps['LapTime'].notna())
        & (laps['LapTime'] > pd.Timedelta(0))
        & (laps['LapTime'] <= max_acceptable_lap)
    ].copy()

    if valid_laps.empty:
        result = pd.DataFrame({'Driver': all_drivers})
        result[col_pace] = np.nan
        result[col_est_fuel] = np.nan
        return result

    valid_laps['LapTime_s'] = valid_laps['LapTime'].dt.total_seconds()
    
    # ── Parámetros Físicos F1 ───────────────────────────────────────────────
    FUEL_CONSUMPTION_PER_LAP = 1.5  # kg burned per lap
    FUEL_MARGIN_KG = 5.0            # safety margin in the tank
    FUEL_PENALTY_PER_KG = 0.03      # seconds lost per kg (0.3s per 10kg)
    
    if compound.upper() == 'SOFT':
        deg_correction = 0.12
    elif compound.upper() == 'HARD':
        deg_correction = 0.05
    else:
        deg_correction = 0.08 

    # Sort to ensure chronological order within stints
    valid_laps = valid_laps.sort_values(by=['Driver', 'Stint', 'LapNumber'])

    def calculate_true_base_pace(df: pd.DataFrame) -> pd.Series:
        if len(df) < window_size:
            return pd.Series({col_pace: np.nan, col_est_fuel: np.nan})
            
        # Estimate how much fuel they must have started with based on stint length
        total_stint_laps = len(df)
        start_fuel_kg = (total_stint_laps * FUEL_CONSUMPTION_PER_LAP) + FUEL_MARGIN_KG
        
        # Calculate lap-by-lap fuel weight and remove both tire and fuel penalties
        # Enumerate gives us the lap index (0, 1, 2...) within the valid stint
        corrected_lap_times = []
        for i, row in enumerate(df.itertuples()):
            current_fuel_kg = start_fuel_kg - (i * FUEL_CONSUMPTION_PER_LAP)
            
            # Time lost due to the weight of fuel
            fuel_time_penalty = current_fuel_kg * FUEL_PENALTY_PER_KG
            
            # Time lost due to tire age
            tire_time_penalty = row.TyreLife * deg_correction
            
            # The theoretical lap time if the car had 0kg fuel and brand new tires
            lap_time_0kg = row.LapTime_s - tire_time_penalty - fuel_time_penalty
            corrected_lap_times.append(lap_time_0kg)
            
        df_calc = pd.DataFrame({'LapTime_0kg': corrected_lap_times, 'LapNumber': df['LapNumber'].values})
        
        # Find the best consecutive window of True Pace
        rolling_avg = df_calc['LapTime_0kg'].rolling(window=window_size).mean()
        
        rolling_lap_max = df_calc['LapNumber'].rolling(window=window_size).max()
        rolling_lap_min = df_calc['LapNumber'].rolling(window=window_size).min()
        is_strictly_consecutive = (rolling_lap_max - rolling_lap_min) == (window_size - 1)
        
        valid_windows = rolling_avg[is_strictly_consecutive]
        
        if valid_windows.empty:
            return pd.Series({col_pace: np.nan, col_est_fuel: start_fuel_kg})
            
        return pd.Series({
            col_pace: valid_windows.min(), 
            col_est_fuel: start_fuel_kg
        })

    # Apply calculations per stint
    stint_stats = (
        valid_laps.groupby(['Driver', 'Stint'])
        .apply(calculate_true_base_pace, include_groups=False)
        .reset_index()
    )

    if col_pace not in stint_stats.columns:
        stint_stats[col_pace] = np.nan
        stint_stats[col_est_fuel] = np.nan

    driver_stats = (
        stint_stats.groupby('Driver')
        .agg({
            col_pace: 'min',       # Take their absolute best 0kg pace
            col_est_fuel: 'max'    # Take the fuel load from their longest stint
        })
        .reset_index()
    )

    result = (
        pd.DataFrame({'Driver': all_drivers})
        .merge(driver_stats, on='Driver', how='left')
    )

    # Sort from fastest Base Pace (lowest time) to slowest
    return result.sort_values(col_pace).reset_index(drop=True)

def get_ers_efficiency_proxy(year: int, gp: str, session_type: str) -> pd.DataFrame:
    """
    Calculates an ERS Efficiency Proxy by analyzing micro-telemetry of the fastest lap.
    It measures the ratio of time spent at Full Throttle (Deploy) vs Braking (Recovery).
    Returns a delta relative to the field median.
    
    Positive proxy = Highly efficient (spends more time deploying relative to recovering).
    Negative proxy = Inefficient (heavy braking, potentially clipping or poor traction).
    """
    session = fastf1.get_session(year, gp, session_type)
    # TELEMETRY MUST BE TRUE FOR THIS FUNCTION
    session.load(telemetry=True, weather=False, messages=False)
    
    prefix = session_type.lower()
    col_proxy = f'{prefix}_ers_efficiency_proxy'
    
    laps = session.laps.pick_quicklaps().copy()
    drivers = laps['Driver'].unique()
    
    ers_data = []

    for drv in drivers:
        drv_laps = laps.pick_drivers(drv)
        if drv_laps.empty:
            continue
            
        # Get the absolute fastest lap for the driver to see maximum ERS mapping
        best_lap = drv_laps.loc[drv_laps['LapTime'].idxmin()]
        
        try:
            tel = best_lap.get_telemetry()
        except:
            continue
            
        if tel.empty:
            continue

        # Calculate time elapsed between each telemetry sample (typically 0.001s - 0.05s)
        tel['Time_delta'] = tel['Time'].dt.total_seconds().diff().fillna(0)

        # MGU-K Recovery Phase: Time spent with brake pedal applied
        braking_time = tel.loc[tel['Brake'] > 0, 'Time_delta'].sum()

        # ERS Deployment Phase: Time spent essentially at full throttle (>95%)
        accel_time = tel.loc[tel['Throttle'] >= 95, 'Time_delta'].sum()

        if braking_time > 0:
            # Raw ratio of Deploy vs Recovery
            ers_ratio = accel_time / braking_time
        else:
            ers_ratio = np.nan

        ers_data.append({
            'Driver': drv,
            'braking_time_s': braking_time,
            'full_throttle_time_s': accel_time,
            'ers_ratio_raw': ers_ratio
        })

    df = pd.DataFrame(ers_data)
    
    if df.empty:
        return df

    # Calculate field median to establish the baseline
    median_ratio = df['ers_ratio_raw'].median()
    
    # Calculate the Proxy: Deviation from the field average
    # Positive means more efficient than average, negative means less efficient
    df[col_proxy] = df['ers_ratio_raw'] - median_ratio

    # Sort from most efficient to least efficient
    df = df.sort_values(col_proxy, ascending=False).reset_index(drop=True)
    
    return df[['Driver', 'braking_time_s', 'full_throttle_time_s', col_proxy]]

##METRICAS 2026
def get_lift_and_coast_laps(year: int, gp: str, session_type: str = 'FP2', min_laps: int = 5) -> pd.DataFrame:
    """
    Calculates the average time (in seconds) per lap a driver spends doing 'Lift & Coast' 
    during their primary long run.
    
    Universal L&C Definition: Speed > 250 km/h AND Throttle < 20% AND Brakes == 0.
    High values indicate battery starvation, severe fuel saving, or PU thermal management.
    """
    session = fastf1.get_session(year, gp, session_type)
    # Telemetry must be loaded for pedal inputs
    session.load(telemetry=True, weather=False, messages=False)
    
    prefix = session_type.lower()
    col_lc_time = f'{prefix}_avg_lift_coast_time_s'
    
    laps = session.laps.copy()
    all_drivers = laps['Driver'].unique()
    
    # Filter for valid racing laps (long runs)
    valid_laps = laps[
        (laps['TrackStatus'] == '1') & 
        (laps['PitOutTime'].isna()) & 
        (laps['PitInTime'].isna()) &
        (laps['LapTime'].notna()) &
        (laps['LapTime'] > pd.Timedelta(0))
    ].copy()
    
    if valid_laps.empty:
        result = pd.DataFrame({'Driver': all_drivers, col_lc_time: np.nan})
        return result

    # Identify the longest stint for each driver
    stint_counts = valid_laps.groupby(['Driver', 'Stint']).size()
    long_runs = stint_counts[stint_counts >= min_laps].reset_index()
    
    results = []
    
    for drv in all_drivers:
        drv_long_runs = long_runs[long_runs['Driver'] == drv]
        
        if drv_long_runs.empty:
            results.append({'Driver': drv, col_lc_time: np.nan})
            continue
            
        # Select their primary long run
        best_stint = drv_long_runs.sort_values(0, ascending=False).iloc[0]['Stint']
        drv_laps = valid_laps[(valid_laps['Driver'] == drv) & (valid_laps['Stint'] == best_stint)]
        
        total_lc_time = 0
        valid_lap_count = 0
        
        for _, lap in drv_laps.iterrows():
            try:
                tel = lap.get_telemetry()
                if tel.empty:
                    continue
                    
                tel['Time_delta'] = tel['Time'].dt.total_seconds().diff().fillna(0)
                
                # The Physical Rule for Lift & Coast
                lc_mask = (tel['Speed'] > 250) & (tel['Throttle'] < 20) & (tel['Brake'] == 0)
                lap_lc_time = tel.loc[lc_mask, 'Time_delta'].sum()
                
                total_lc_time += lap_lc_time
                valid_lap_count += 1
            except Exception:
                continue
        
        if valid_lap_count > 0:
            avg_lc = total_lc_time / valid_lap_count
        else:
            avg_lc = np.nan
            
        results.append({'Driver': drv, col_lc_time: avg_lc})
        
    df = pd.DataFrame(results)
    
    # Sort from highest L&C (most conservative/starved) to lowest (flat out)
    return df.sort_values(col_lc_time, ascending=False).reset_index(drop=True)

def get_pu_deployment_asymmetry(year: int, gp: str, session_type: str = 'FP2') -> pd.DataFrame:
    """
    Calculates the ratio between Sector 1 and Sector 3 times for the fastest lap.
    Acts as a proxy for Power Unit (PU) deployment strategy and aero balance.
    
    A higher ratio indicates more time spent in S1 relative to S3 (saving battery for S3).
    A lower ratio indicates aggressive deployment in S1 and clipping in S3.
    """
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=False, weather=False, messages=False)
    
    prefix = session_type.lower()
    col_s1 = f'{prefix}_best_s1_s'
    col_s3 = f'{prefix}_best_s3_s'
    col_ratio = f'{prefix}_s1_vs_s3_ratio'
    col_asymmetry = f'{prefix}_pu_asymmetry_delta'
    
    laps = session.laps.copy()
    all_drivers = laps['Driver'].unique()

    # Filter for valid push laps without pit stops
    valid_laps = laps[
        (laps['TrackStatus'] == '1')
        & (laps['PitOutTime'].isna())
        & (laps['PitInTime'].isna())
        & (laps['LapTime'].notna())
        & (laps['Sector1Time'].notna())
        & (laps['Sector3Time'].notna())
    ].copy()

    if valid_laps.empty:
        result = pd.DataFrame({'Driver': all_drivers})
        result[col_ratio] = np.nan
        result[col_asymmetry] = np.nan
        return result

    # Find the absolute best lap for each driver to see maximum PU deployment
    best_idx = valid_laps.groupby('Driver')['LapTime'].idxmin()
    best_laps = valid_laps.loc[best_idx].copy()
    
    # Convert timedelta to purely numerical seconds for ML algorithms
    best_laps[col_s1] = best_laps['Sector1Time'].dt.total_seconds()
    best_laps[col_s3] = best_laps['Sector3Time'].dt.total_seconds()
    
    # Calculate the raw ratio (S1 Time / S3 Time)
    best_laps[col_ratio] = best_laps[col_s1] / best_laps[col_s3]
    
    # Calculate field median to establish the baseline strategy
    median_ratio = best_laps[col_ratio].median()
    
    # Calculate asymmetry (deviation from the field's median strategy)
    # Positive delta: Bias towards S3 deployment (slower S1)
    # Negative delta: Bias towards S1 deployment (slower S3)
    best_laps[col_asymmetry] = best_laps[col_ratio] - median_ratio

    # Keep only the relevant features
    driver_stats = best_laps[['Driver', col_s1, col_s3, col_ratio, col_asymmetry]]

    result = (
        pd.DataFrame({'Driver': all_drivers})
        .merge(driver_stats, on='Driver', how='left')
    )

    # Sort to group similar engine mapping strategies together
    return result.sort_values(col_asymmetry, ascending=False).reset_index(drop=True)

def get_speed_trap_variance(year: int, gp: str, session_type: str = 'FP2', min_laps: int = 5) -> pd.DataFrame:
    """
    Calculates the standard deviation (variance proxy) of the maximum speed 
    reached per lap during a driver's primary long run.
    
    High variance indicates erratic ERS deployment, clipping, or heavy traffic.
    Low variance indicates a perfectly tuned ERS map and predictable race pace.
    """
    session = fastf1.get_session(year, gp, session_type)
    # Telemetry is strictly required to find the absolute max speed of each lap
    session.load(telemetry=True, weather=False, messages=False)
    
    prefix = session_type.lower()
    col_std = f'{prefix}_speed_trap_std_kmh'
    col_mean = f'{prefix}_speed_trap_mean_kmh'
    
    laps = session.laps.copy()
    all_drivers = laps['Driver'].unique()
    
    # Filter for valid push laps in the long run
    valid_laps = laps[
        (laps['TrackStatus'] == '1') & 
        (laps['PitOutTime'].isna()) & 
        (laps['PitInTime'].isna()) &
        (laps['LapTime'].notna())
    ].copy()
    
    if valid_laps.empty:
        return pd.DataFrame({'Driver': all_drivers, col_std: np.nan, col_mean: np.nan})

    # Identify the longest stint per driver to evaluate race simulation
    stint_counts = valid_laps.groupby(['Driver', 'Stint']).size()
    long_runs = stint_counts[stint_counts >= min_laps].reset_index()
    
    results = []
    
    for drv in all_drivers:
        drv_long_runs = long_runs[long_runs['Driver'] == drv]
        
        if drv_long_runs.empty:
            results.append({'Driver': drv, col_std: np.nan, col_mean: np.nan})
            continue
            
        # Select their primary long run
        best_stint = drv_long_runs.sort_values(0, ascending=False).iloc[0]['Stint']
        drv_laps = valid_laps[(valid_laps['Driver'] == drv) & (valid_laps['Stint'] == best_stint)]
        
        lap_top_speeds = []
        
        for _, lap in drv_laps.iterrows():
            try:
                tel = lap.get_telemetry()
                if not tel.empty:
                    # Find the absolute maximum speed registered in the telemetry array
                    max_speed = tel['Speed'].max()
                    lap_top_speeds.append(max_speed)
            except Exception:
                continue
        
        # Calculate statistical variance metrics if we have enough laps
        if len(lap_top_speeds) > 1:
            speed_std = np.std(lap_top_speeds, ddof=1)
            speed_mean = np.mean(lap_top_speeds)
        else:
            speed_std = np.nan
            speed_mean = np.nan
            
        results.append({'Driver': drv, col_std: speed_std, col_mean: speed_mean})
        
    df = pd.DataFrame(results)
    
    # Sort from highest variance (most inconsistent/erratic) to lowest
    return df.sort_values(col_std, ascending=False).reset_index(drop=True)

#fine tuning
def get_qualy_sim_delta(year: int, gp: str, session_type: str = 'FP3', compound: str = 'SOFT') -> pd.DataFrame:
    """
    Calculates the Qualifying Simulation Delta (in seconds) for each driver.
    Finds each driver's absolute fastest lap on the specified compound and 
    compares it to the overall fastest lap of the session.
    
    The leader will have a delta of 0.000.
    """
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=False, weather=False, messages=False)
    
    prefix = session_type.lower()
    comp_lower = compound.lower()
    
    col_laptime = f'{prefix}_{comp_lower}_best_lap_s'
    col_delta = f'{prefix}_{comp_lower}_best_lap_delta'
    
    laps = session.laps.copy()
    all_drivers = laps['Driver'].unique()

    # Apply quality filters for valid push laps (Qualy sims)
    valid_laps = laps[
        (laps['Compound'] == compound.upper())
        & (laps['TrackStatus'] == '1')
        & (laps['PitOutTime'].isna())
        & (laps['PitInTime'].isna())
        & (laps['LapTime'].notna())
    ].copy()

    # DEFENSIVE CHECK: Short-circuit if session was a washout or no valid laps exist
    if valid_laps.empty:
        result = pd.DataFrame({'Driver': all_drivers})
        result[col_laptime] = np.nan
        result[col_delta] = np.nan
        return result

    # Find the absolute best lap time for each driver
    driver_bests = (
        valid_laps.groupby('Driver')['LapTime']
        .min()
        .reset_index()
    )
    
    # Identify the absolute fastest lap of the entire session
    overall_fastest_lap = driver_bests['LapTime'].min()

    # Calculate metrics in strictly numerical format (seconds) for Machine Learning
    driver_bests[col_laptime] = driver_bests['LapTime'].dt.total_seconds()
    driver_bests[col_delta] = (driver_bests['LapTime'] - overall_fastest_lap).dt.total_seconds()

    # Drop the Timedelta column and prepare final merge
    driver_stats = driver_bests[['Driver', col_laptime, col_delta]]

    # Reintegrate all drivers (those who crashed or didn't run will get NaN)
    result = (
        pd.DataFrame({'Driver': all_drivers})
        .merge(driver_stats, on='Driver', how='left')
    )

    # Sort from fastest (Delta 0.000) to slowest
    return result.sort_values(col_delta).reset_index(drop=True)

def get_fp3_vs_fp2_improvement(year: int, gp: str, compound: str = 'SOFT') -> pd.DataFrame:
    """
    Calculates the overnight setup improvement from FP2 to FP3.
    Formula: FP2 Best Lap - FP3 Best Lap (in seconds).
    
    A positive value indicates the car got faster (improved setup + track evolution).
    A negative value indicates the car got slower (failed setup, bad correlation, or wet track).
    """
    # Load both sessions back-to-back
    fp2 = fastf1.get_session(year, gp, 'FP2')
    fp3 = fastf1.get_session(year, gp, 'FP3')
    
    fp2.load(telemetry=False, weather=False, messages=False)
    fp3.load(telemetry=False, weather=False, messages=False)
    
    comp_lower = compound.lower()
    
    def get_best_laps(session_laps: pd.DataFrame, prefix: str) -> pd.DataFrame:
        """Helper to extract the absolute best valid lap for each driver in a session."""
        valid_laps = session_laps[
            (session_laps['Compound'] == compound.upper())
            & (session_laps['TrackStatus'] == '1')
            & (session_laps['PitOutTime'].isna())
            & (session_laps['PitInTime'].isna())
            & (session_laps['LapTime'].notna())
        ].copy()
        
        if valid_laps.empty:
            return pd.DataFrame({'Driver': session_laps['Driver'].unique(), f'{prefix}_{comp_lower}_best_s': np.nan})
            
        # Group by driver and find minimum lap time
        best_laps = (
            valid_laps.groupby('Driver')['LapTime']
            .min()
            .dt.total_seconds()
            .reset_index()
        )
        return best_laps.rename(columns={'LapTime': f'{prefix}_{comp_lower}_best_s'})

    # Extract best laps from both sessions
    fp2_bests = get_best_laps(fp2.laps, 'fp2')
    fp3_bests = get_best_laps(fp3.laps, 'fp3')
    
    # Consolidate all drivers that participated in either session
    all_drivers = pd.Series(
        list(set(fp2.laps['Driver'].unique()).union(set(fp3.laps['Driver'].unique()))), 
        name='Driver'
    )
    df_all = pd.DataFrame(all_drivers)
    
    # Merge the FP2 and FP3 data into a single DataFrame
    result = (
        df_all
        .merge(fp2_bests, on='Driver', how='left')
        .merge(fp3_bests, on='Driver', how='left')
    )
    
    # Calculate the Overnight Improvement
    # Example: FP2 (91.5s) - FP3 (90.5s) = +1.0s (Improved by 1 second)
    col_improvement = f'fp3_vs_fp2_{comp_lower}_improvement'
    result[col_improvement] = result[f'fp2_{comp_lower}_best_s'] - result[f'fp3_{comp_lower}_best_s']
    
    # Sort by the most improved drivers at the top
    return result.sort_values(col_improvement, ascending=False).reset_index(drop=True)

def get_sector_improvement_vs_fp2(year: int, gp: str, compound: str = 'SOFT') -> pd.DataFrame:
    """
    Calculates the overnight setup improvement broken down by sector (FP2 to FP3).
    Formula: FP2 Sector Time - FP3 Sector Time (in seconds).
    
    A positive value means the sector got faster (improvement).
    A negative value means the sector got slower (lost time).
    Reveals aerodynamic trade-offs (e.g., stripping wing for straight line speed).
    """
    fp2 = fastf1.get_session(year, gp, 'FP2')
    fp3 = fastf1.get_session(year, gp, 'FP3')
    
    fp2.load(telemetry=False, weather=False, messages=False)
    fp3.load(telemetry=False, weather=False, messages=False)
    
    comp_lower = compound.lower()
    
    def get_best_lap_sectors(session_laps: pd.DataFrame, prefix: str) -> pd.DataFrame:
        """Finds the absolute best valid lap and extracts its sector times."""
        valid_laps = session_laps[
            (session_laps['Compound'] == compound.upper())
            & (session_laps['TrackStatus'] == '1')
            & (session_laps['PitOutTime'].isna())
            & (session_laps['PitInTime'].isna())
            & (session_laps['LapTime'].notna())
            & (session_laps['Sector1Time'].notna())
            & (session_laps['Sector2Time'].notna())
            & (session_laps['Sector3Time'].notna())
        ].copy()
        
        if valid_laps.empty:
            return pd.DataFrame({'Driver': session_laps['Driver'].unique()})
            
        # Get index of the fastest lap for each driver
        best_idx = valid_laps.groupby('Driver')['LapTime'].idxmin()
        best_laps = valid_laps.loc[best_idx].copy()
        
        # Extract purely the seconds for ML calculation
        res = pd.DataFrame({
            'Driver': best_laps['Driver'],
            f'{prefix}_s1_s': best_laps['Sector1Time'].dt.total_seconds(),
            f'{prefix}_s2_s': best_laps['Sector2Time'].dt.total_seconds(),
            f'{prefix}_s3_s': best_laps['Sector3Time'].dt.total_seconds()
        })
        return res

    fp2_sectors = get_best_lap_sectors(fp2.laps, 'fp2')
    fp3_sectors = get_best_lap_sectors(fp3.laps, 'fp3')
    
    # Consolidate all drivers
    all_drivers = pd.Series(
        list(set(fp2.laps['Driver'].unique()).union(set(fp3.laps['Driver'].unique()))), 
        name='Driver'
    )
    
    df = pd.DataFrame(all_drivers)
    df = (df.merge(fp2_sectors, on='Driver', how='left')
            .merge(fp3_sectors, on='Driver', how='left'))
    
    # Calculate the Delta Improvements (FP2 - FP3)
    # E.g., FP2 Sector 1 (30.5s) - FP3 Sector 1 (30.0s) = +0.5s improvement
    df['fp3_s1_delta_vs_fp2'] = df['fp2_s1_s'] - df['fp3_s1_s']
    df['fp3_s2_delta_vs_fp2'] = df['fp2_s2_s'] - df['fp3_s2_s']
    df['fp3_s3_delta_vs_fp2'] = df['fp2_s3_s'] - df['fp3_s3_s']
    
    # Calculate total to sort by the biggest overall improver
    df['total_imp'] = df['fp3_s1_delta_vs_fp2'] + df['fp3_s2_delta_vs_fp2'] + df['fp3_s3_delta_vs_fp2']
    
    # Clean up output for the final Dataset
    final_cols = ['Driver', 'fp3_s1_delta_vs_fp2', 'fp3_s2_delta_vs_fp2', 'fp3_s3_delta_vs_fp2']
    
    return df.sort_values('total_imp', ascending=False)[final_cols].reset_index(drop=True)

def get_fp3_qualy_sim_context(year: int, gp: str, session_type: str = 'FP3') -> pd.DataFrame:
    """
    Extracts high-fidelity context for the qualifying simulation.
    Evaluates the compound and the exact physical degradation (TyreLife) 
    at the moment the fastest lap was set to separate true Qualy sims 
    from compromised runs.
    """
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=False, weather=False, messages=False)
    
    prefix = session_type.lower()
    col_tyre = f'{prefix}_best_lap_compound'
    col_age = f'{prefix}_best_lap_tyre_age'
    col_true_sim_flag = f'{prefix}_is_true_qualy_sim'
    
    laps = session.laps.copy()
    all_drivers = laps['Driver'].unique()

    valid_laps = laps[
        (laps['TrackStatus'] == '1')
        & (laps['PitOutTime'].isna())
        & (laps['PitInTime'].isna())
        & (laps['LapTime'].notna())
    ].copy()

    if valid_laps.empty:
        result = pd.DataFrame({'Driver': all_drivers})
        result[col_tyre] = 'UNKNOWN'
        result[col_age] = np.nan
        result[col_true_sim_flag] = 0
        return result

    best_idx = valid_laps.groupby('Driver')['LapTime'].idxmin()
    best_laps = valid_laps.loc[best_idx].copy()

    # Feature 1: The Compound
    best_laps[col_tyre] = best_laps['Compound']
    
    # Feature 2: Physical Degradation (Age of the tyre in laps)
    # Convert to numeric, handle potential API missing data
    best_laps[col_age] = pd.to_numeric(best_laps['TyreLife'], errors='coerce').fillna(1.0)
    
    # Feature 3: The True Qualy Sim Flag (Strict ML rule)
    # A true qualy sim is a SOFT tyre with 3 laps or less of age 
    # (Out lap + Prep lap + Push lap). Anything older is compromised.
    best_laps[col_true_sim_flag] = (
        (best_laps['Compound'] == 'SOFT') & 
        (best_laps[col_age] <= 3.0)
    ).astype(int)

    driver_stats = best_laps[['Driver', col_tyre, col_age, col_true_sim_flag]]

    result = (
        pd.DataFrame({'Driver': all_drivers})
        .merge(driver_stats, on='Driver', how='left')
    )
    
    result[col_tyre] = result[col_tyre].fillna('NONE')
    result[col_age] = result[col_age].fillna(100.0) # Penalize drivers with no data
    result[col_true_sim_flag] = result[col_true_sim_flag].fillna(0).astype(int)

    return result

def get_track_evolution(year: int, gp: str, session_type: str = 'FP3') -> pd.DataFrame:
    """
    Calculates the global track evolution over the course of the session.
    Splits the session dynamically into halves and compares the absolute best 
    lap of the early phase vs the late phase.
    
    A positive value (e.g., 1.5s) means massive rubbering-in (track getting faster).
    A negative value means the track got slower (rain, wind, or cooling temperatures).
    """
    session = fastf1.get_session(year, gp, session_type)
    session.load(telemetry=False, weather=False, messages=False)
    
    prefix = session_type.lower()
    col_evo = f'{prefix}_track_evolution_s'
    
    laps = session.laps.copy()
    all_drivers = laps['Driver'].unique()

    # Filter for valid push laps
    valid_laps = laps[
        (laps['TrackStatus'] == '1') &
        (laps['PitOutTime'].isna()) &
        (laps['PitInTime'].isna()) &
        (laps['LapTime'].notna())
    ].copy()

    if valid_laps.empty:
        return pd.DataFrame({'Driver': all_drivers, col_evo: np.nan})

    # Divide the session temporally (not by lap numbers, as drivers run at different times)
    session_start = valid_laps['Time'].min()
    session_end = valid_laps['Time'].max()
    midpoint = session_start + (session_end - session_start) / 2

    early_laps = valid_laps[valid_laps['Time'] <= midpoint]
    late_laps = valid_laps[valid_laps['Time'] > midpoint]

    if early_laps.empty or late_laps.empty:
        track_evo = np.nan
    else:
        # Convert Timedelta to purely numerical seconds
        best_early_s = early_laps['LapTime'].min().total_seconds()
        best_late_s = late_laps['LapTime'].min().total_seconds()
        
        # Improvement = Early Lap - Late Lap. (e.g., 92.0s - 90.5s = +1.5s Evolution)
        track_evo = best_early_s - best_late_s

    # Broadcast this global contextual variable to every driver in the dataset
    df = pd.DataFrame({'Driver': all_drivers})
    df[col_evo] = track_evo

    return df

#podios
def get_grid_position_features(year: int, gp: str, session_type: str = 'R') -> pd.DataFrame:
    """
    Extracts the final starting grid positions for the race and creates 
    highly predictive engineered features for Machine Learning models.
    
    Handles edge cases like pit lane starts (usually represented as 0 in FastF1).
    Note: We use the 'R' (Race) session because it contains the final grid 
    after all grid penalties have been applied.
    """
    session = fastf1.get_session(year, gp, session_type)
    # We only need the results table, no telemetry required
    session.load(telemetry=False, weather=False, messages=False)
    
    results = session.results
    
    if results is None or results.empty:
        return pd.DataFrame({'Driver': [], 'grid_position': []})
        
    df = pd.DataFrame({
        'Driver': results['Abbreviation'],
        'raw_grid': results['GridPosition']
    })
    
    # Ensure numeric types
    df['raw_grid'] = pd.to_numeric(df['raw_grid'], errors='coerce')
    
    # Feature 1: Pit Lane Start Flag
    # FastF1 assigns 0 to pit lane starters. We capture this as a distinct binary event.
    df['started_from_pitlane'] = (df['raw_grid'] == 0).astype(int)
    
    # Feature 2: Adjusted Grid Position (Ordinal correction)
    # Models interpret lower numbers as better. A 0 would break the model.
    # We assign pit lane starters to 21 (behind the grid).
    df['grid_position'] = np.where(df['raw_grid'] == 0, 21, df['raw_grid'])
    # Handle DNS (Did Not Start) or NaNs by placing them at the back
    df['grid_position'] = df['grid_position'].fillna(21)
    
    # Feature 3: Front Row Flag
    # Being in P1 or P2 guarantees clean air into Turn 1. This is a non-linear advantage.
    df['is_front_row'] = (df['grid_position'] <= 2).astype(int)
    
    # Feature 4: Top 10 Flag (Points Contention)
    # Starting in the top 10 changes race strategy (e.g., tire choices).
    df['started_top_10'] = (df['grid_position'] <= 10).astype(int)
    
    final_cols = [
        'Driver', 
        'grid_position', 
        'is_front_row', 
        'started_top_10', 
        'started_from_pitlane'
    ]
    
    return df[final_cols].sort_values('grid_position').reset_index(drop=True)

def get_qualy_deltas(year: int, gp: str) -> pd.DataFrame:
    """
    Extracts the Qualifying deltas to the Pole Position time.
    Calculates both the strict Q3 delta and an overall Best Qualy delta
    to avoid NaNs for drivers eliminated in Q1/Q2.
    """
    # Load Qualifying session
    session = fastf1.get_session(year, gp, 'Q')
    # Official timing is in results; no heavy telemetry needed
    session.load(telemetry=False, weather=False, messages=False)

    results = session.results.copy()

    if results is None or results.empty:
        return pd.DataFrame()

    df = pd.DataFrame({'Driver': results['Abbreviation']})

    # 1. Identify the Pole Time
    # By FIA rules, Pole is the fastest valid time set in Q3
    pole_time = results['Q3'].min()
    pole_time_s = pole_time.total_seconds()

    # 2. Strict Q3 Delta (Will have NaNs for Q1/Q2 knockouts)
    df['q3_time_s'] = results['Q3'].dt.total_seconds()
    df['q3_delta_to_pole'] = df['q3_time_s'] - pole_time_s

    # 3. ML-Optimized Overall Delta (Fallback feature)
    # Find the absolute best time for each driver across any phase (Q1, Q2, Q3)
    best_q_times = results[['Q1', 'Q2', 'Q3']].min(axis=1)
    df['best_q_time_s'] = best_q_times.dt.total_seconds()
    
    # Compare everyone's absolute best lap to the Pole lap
    df['best_q_delta_to_pole'] = df['best_q_time_s'] - pole_time_s

    # 4. Context Label: Where did they get eliminated?
    def get_elimination(row):
        if pd.notna(row['Q3']): return 'Q3'
        if pd.notna(row['Q2']): return 'Q2'
        if pd.notna(row['Q1']): return 'Q1'
        return 'DNQ'
        
    df['reached_session'] = results.apply(get_elimination, axis=1)

    return df

def get_team_info(year: int, gp: str, session_type: str) -> pd.DataFrame:
    """
    Extracts the team and driver mapping using fastf1.
    """
    try:
        session = fastf1.get_session(year, gp, session_type)
        session.load(telemetry=False, weather=False, messages=False)
        res = session.results
        
        teams = []
        for _, row in res.iterrows():
            teams.append({
                'Driver': row['Abbreviation'],
                'Team': row['TeamName']
            })
        return pd.DataFrame(teams)
    except Exception as e:
        print(f"Error obtaining team info for {year} {gp}: {e}")
        return pd.DataFrame(columns=['Driver', 'Team'])

def get_qualy_target_percentile(year: int, gp: str, target_session: str = 'Q') -> pd.DataFrame:
    """
    Gets the Qualifying (Q or SQ) results to calculate a Percentile Target.
    """
    try:
        session = fastf1.get_session(year, gp, target_session)
        session.load(telemetry=False, weather=False, messages=True)
        res = session.results
        
        q_data = []
        fastest_q_time = None
        
        cols_to_check = [c for c in ['Q1','Q2','Q3','SQ1','SQ2','SQ3'] if c in res.columns]
        for _, row in res.iterrows():
            times = [row[c] for c in cols_to_check if c in row and pd.notnull(row[c])]
            if times:
                best_time = min(times)
                if fastest_q_time is None or best_time < fastest_q_time:
                    fastest_q_time = best_time
        
        for _, row in res.iterrows():
            driver = row['Abbreviation']
            pos = row['Position']
            
            times = [row[c] for c in cols_to_check if c in row and pd.notnull(row[c])]
            q_delta = np.nan
            if times and fastest_q_time is not None:
                q_delta = (min(times) - fastest_q_time).total_seconds()
                
            q_data.append({
                'Driver': driver,
                'Qualy_Position': pos,
                'Qualy_Delta': q_delta
            })
            
        df_q = pd.DataFrame(q_data)
        df_q['Target_Percentile'] = df_q['Qualy_Delta'].rank(pct=True)
        return df_q
    except Exception as e:
        print(f"Error extracting {target_session} for {year} {gp}: {e}")
        return None

    # Cleanup and sort by the closest to pole
    final_cols = ['Driver', 'reached_session', 'q3_delta_to_pole', 'best_q_delta_to_pole']
    return df[final_cols].sort_values('best_q_delta_to_pole').reset_index(drop=True)

def get_q3_participation_flag(year: int, gp: str) -> pd.DataFrame:
    """
    Creates a binary feature indicating if a driver reached Q3.
    1 = Reached Q3 (Elite pace/Contender)
    0 = Eliminated in Q1 or Q2
    
    This is highly optimized for the first split in Decision Tree models.
    """
    session = fastf1.get_session(year, gp, 'Q')
    # No telemetry needed, just official classification
    session.load(telemetry=False, weather=False, messages=False)

    results = session.results.copy()

    if results is None or results.empty:
        return pd.DataFrame({'Driver': [], 'q3_participation': []})

    df = pd.DataFrame({'Driver': results['Abbreviation']})

    # In FastF1, if a driver didn't reach Q3, their Q3 time is NaT (Not a Time)
    # We use .notna() to check if they advanced, and .astype(int) turns True/False into 1/0
    df['q3_participation'] = results['Q3'].notna().astype(int)

    # Sort to show the Q3 contenders at the top
    return df.sort_values('q3_participation', ascending=False).reset_index(drop=True)

def get_qualy_vs_fp3_improvement(year: int, gp: str) -> pd.DataFrame:
    """
    Calculates the 'Time Found' from FP3 to Qualifying.
    Formula: FP3 Best Lap - Qualy Best Lap (in seconds).
    
    A large positive value indicates significant engine mode step-up ("Sandbagging" in FP3).
    A small or negative value indicates the team was already at the limit in FP3, 
    or the driver made a mistake in Qualifying.
    """
    fp3 = fastf1.get_session(year, gp, 'FP3')
    q = fastf1.get_session(year, gp, 'Q')
    
    # Load both sessions. Qualy uses results, FP3 needs laps to find the best time.
    fp3.load(telemetry=False, weather=False, messages=False)
    q.load(telemetry=False, weather=False, messages=False)
    
    # 1. Get the absolute best valid lap for each driver in FP3
    fp3_laps = fp3.laps.copy()
    valid_fp3 = fp3_laps[
        (fp3_laps['TrackStatus'] == '1') & 
        (fp3_laps['PitOutTime'].isna()) & 
        (fp3_laps['PitInTime'].isna()) & 
        (fp3_laps['LapTime'].notna())
    ]
    
    if valid_fp3.empty:
        fp3_bests = pd.DataFrame({'Driver': fp3_laps['Driver'].unique(), 'fp3_best_s': np.nan})
    else:
        fp3_bests = valid_fp3.groupby('Driver')['LapTime'].min().dt.total_seconds().reset_index()
        fp3_bests.rename(columns={'LapTime': 'fp3_best_s'}, inplace=True)
        
    # 2. Get the Qualy times from the official FIA classification
    q_results = q.results.copy()
    if q_results is None or q_results.empty:
        q_times = pd.DataFrame({'Driver': fp3_bests['Driver'].unique(), 'q3_time_s': np.nan, 'best_q_time_s': np.nan})
    else:
        q_times = pd.DataFrame({'Driver': q_results['Abbreviation']})
        q_times['q3_time_s'] = q_results['Q3'].dt.total_seconds()
        
        # ML Armor: Best overall Qualy lap across all phases
        best_q = q_results[['Q1', 'Q2', 'Q3']].min(axis=1)
        q_times['best_q_time_s'] = best_q.dt.total_seconds()
        
    # 3. Consolidate and Calculate Deltas
    df = pd.merge(fp3_bests, q_times, on='Driver', how='outer')
    
    # Improvement = FP3 - Qualy. 
    # E.g., FP3 (91.0s) - Qualy (89.5s) = +1.5s found
    df['q3_vs_fp3_improvement'] = df['fp3_best_s'] - df['q3_time_s']
    df['best_q_vs_fp3_improvement'] = df['fp3_best_s'] - df['best_q_time_s']
    
    final_cols = ['Driver', 'fp3_best_s', 'best_q_time_s', 'q3_vs_fp3_improvement', 'best_q_vs_fp3_improvement']
    
    # Sort by who found the most time
    return df[final_cols].sort_values('best_q_vs_fp3_improvement', ascending=False).reset_index(drop=True)

def get_best_quali_relative_sector(year: int, gp: str) -> pd.DataFrame:
    """
    Identifies the strongest sector for each driver relative to the field during Qualifying.
    
    1. Finds the absolute best valid lap for each driver across Q1, Q2, Q3.
    2. Extracts S1, S2, S3 times from that lap.
    3. Calculates the delta to the fastest time in each sector across the whole session.
    4. Determines which sector had the smallest delta (their relatively best sector).
    """
    q_session = fastf1.get_session(year, gp, 'Q')
    # Telemetry is needed to get precise sector times for every lap
    q_session.load(telemetry=False, weather=False, messages=False)

    laps = q_session.laps.copy()
    all_drivers = laps['Driver'].unique()

    # Filter for valid push laps (ignoring in/out laps)
    valid_laps = laps[
        (laps['TrackStatus'] == '1') &
        (laps['PitOutTime'].isna()) &
        (laps['PitInTime'].isna()) &
        (laps['LapTime'].notna()) &
        (laps['Sector1Time'].notna()) &
        (laps['Sector2Time'].notna()) &
        (laps['Sector3Time'].notna())
    ].copy()

    if valid_laps.empty:
        return pd.DataFrame({'Driver': all_drivers, 'quali_best_relative_sector': 'NONE'})

    # 1. Find the absolute best lap for each driver
    best_lap_idx = valid_laps.groupby('Driver')['LapTime'].idxmin()
    best_laps = valid_laps.loc[best_lap_idx].copy()

    # 2. Extract sector times in seconds
    best_laps['s1_s'] = best_laps['Sector1Time'].dt.total_seconds()
    best_laps['s2_s'] = best_laps['Sector2Time'].dt.total_seconds()
    best_laps['s3_s'] = best_laps['Sector3Time'].dt.total_seconds()

    # 3. Find the absolute fastest time for each sector in the entire session
    fastest_s1 = best_laps['s1_s'].min()
    fastest_s2 = best_laps['s2_s'].min()
    fastest_s3 = best_laps['s3_s'].min()

    # 4. Calculate relative deltas (Driver Sector Time - Fastest Sector Time)
    best_laps['s1_delta'] = best_laps['s1_s'] - fastest_s1
    best_laps['s2_delta'] = best_laps['s2_s'] - fastest_s2
    best_laps['s3_delta'] = best_laps['s3_s'] - fastest_s3

    # 5. Determine the best relative sector (the one with the smallest delta)
    # We use idxmin along the delta columns to find the column name
    sector_delta_cols = ['s1_delta', 's2_delta', 's3_delta']
    best_laps['best_relative_sector_col'] = best_laps[sector_delta_cols].idxmin(axis=1)

    # Clean up the output to just 'S1', 'S2', 'S3'
    sector_map = {
        's1_delta': 'S1',
        's2_delta': 'S2',
        's3_delta': 'S3'
    }
    best_laps['quali_best_relative_sector'] = best_laps['best_relative_sector_col'].map(sector_map)

    # Prepare final DataFrame
    final_cols = ['Driver', 'quali_best_relative_sector', 's1_delta', 's2_delta', 's3_delta']
    result = best_laps[final_cols]
    
    # Ensure all drivers are present, even if they had no valid laps
    df_all = pd.DataFrame({'Driver': all_drivers})
    df_final = df_all.merge(result, on='Driver', how='left')
    df_final['quali_best_relative_sector'] = df_final['quali_best_relative_sector'].fillna('NONE')

    # Sort to show who dominated each sector
    return df_final.sort_values(['quali_best_relative_sector', 's1_delta']).reset_index(drop=True)

# if __name__ == '__main__':
#     TARGET_SESSION = 'FP2'
    
#     df_best = get_best_lap_delta(2026, 'Japan', TARGET_SESSION)
#     print(df_best.to_string(index=False))
    
#     df_clean = get_clean_laps_count(2026, 'Japan', TARGET_SESSION)
#     print(df_clean.to_string(index=False))
    
#     df_avg = get_compound_avg(2026, 'Japan', TARGET_SESSION, compound='HARD')
#     print(df_avg.to_string(index=False))
    
#     df_sectors = get_sector_deltas(2026, 'Japan', TARGET_SESSION)
#     print(df_sectors.to_string(index=False))
    
#     df_speed = get_max_speed_trap(2026, 'Japan', TARGET_SESSION)
#     print(df_speed.to_string(index=False))
    
#     df_laps_hard = get_laps_on_compound(2026, 'Japan', TARGET_SESSION, compound='HARD')
#     print(df_laps_hard.to_string(index=False))
    
#     df_longrun_vg = get_longrun_avg_pace(2026,'Japan',TARGET_SESSION)
#     print(df_longrun_vg)
    
#     df_longrun_deg_rate = get_longrun_deg_rate(2026,'Japan',TARGET_SESSION, compound='HARD')
#     print(df_longrun_deg_rate)
    
#     df_deg_total = get_longrun_deg_total(2026, 'Japan', TARGET_SESSION, compound='MEDIUM', min_laps=5, expected_stint_length=18)
#     print(df_deg_total.to_string(index=False))
    
#     df_consistency = get_longrun_consistency(2026, 'Japan', TARGET_SESSION, compound='HARD', min_laps=5)
#     print("FP2 Long Run Consistency (Standard Deviation in seconds):")
#     print(df_consistency.to_string(index=False))
    
#     df_compound = get_longrun_compound(2026, 'Japan', TARGET_SESSION, min_laps=5)
#     print("FP2 Long Run Primary Compound:")
#     print(df_compound.to_string(index=False))
    
#     df_fuel_pace = get_fuel_corrected_pace(2026, 'Japan', TARGET_SESSION, compound='MEDIUM', window_size=5)
#     print("FP2 Fuel Corrected Base Pace (0kg Fuel Equivalent):")
#     print(df_fuel_pace.to_string(index=False))
    
#     df_ers = get_ers_efficiency_proxy(2026, 'Japan', TARGET_SESSION)
#     print("FP2 ERS Efficiency Proxy (Delta vs Field):")
#     print(df_ers.to_string(index=False))
    
#     df_lc = get_lift_and_coast_laps(2026, 'Japan', TARGET_SESSION, min_laps=5)
#     print("FP2 Average Lift & Coast Time per Lap (Seconds):")
#     print(df_lc.to_string(index=False))

#     df_speed_var = get_speed_trap_variance(2026, 'Japan', TARGET_SESSION, min_laps=5)
#     print("FP2 Speed Trap Variance (km/h) during Long Runs:")
#     print(df_speed_var.to_string(index=False))

#     df_sector_imp = get_sector_improvement_vs_fp2(2026, 'Japan', compound='SOFT')
#     print("Overnight Sector Improvement (Seconds gained per sector vs FP2):")
#     print(df_sector_imp.to_string(index=False))
        
#     df_qualy_sim = get_qualy_sim_delta(2026, 'Japan', TARGET_SESSION, compound='SOFT')
#     print("FP3 Qualy Sim Pace (Delta to Leader):")
#     print(df_qualy_sim.to_string(index=False))
    
#     df_improvement = get_fp3_vs_fp2_improvement(2026, 'Japan', compound='SOFT')
#     print("Overnight Setup Improvement (Seconds gained from FP2 to FP3):")
#     print(df_improvement.to_string(index=False))
    
#     df_pu = get_pu_deployment_asymmetry(2026, 'Japan', TARGET_SESSION)
#     print("FP2 S1 vs S3 Ratio (PU Deployment Asymmetry):")
#     print(df_pu.to_string(index=False))
    
#     df_tyre = get_fp3_qualy_sim_context(2026, 'Japan', TARGET_SESSION)
#     print("FP3 Best Lap Tyre Compound:")
#     print(df_tyre.to_string(index=False))
    
#     df_evo = get_track_evolution(2026, 'Japan', TARGET_SESSION)
#     print("FP3 Global Track Evolution (Seconds):")
#     print(df_evo.head(5).to_string(index=False))
    
#     df_grid = get_grid_position_features(2026, 'Japan', TARGET_SESSION)
#     print("Final Grid Position Features for ML:")
#     print(df_grid.head(21).to_string(index=False))
    
#     df_qualy = get_qualy_deltas(2026, 'Japan')
#     print("Qualifying Deltas to Pole Position (Seconds):")
#     print(df_qualy.head(15).to_string(index=False))
    
#     df_q3_flag = get_q3_participation_flag(2026, 'Japan')
#     print("Q3 Participation Flag (1 = Yes, 0 = No):")
#     print(df_q3_flag.head(15).to_string(index=False))
    
#     df_jump = get_qualy_vs_fp3_improvement(2026, 'Japan')
#     print("Time Found from FP3 to Qualifying (Seconds):")
#     print(df_jump.head(15).to_string(index=False))
    
#     df_best_sector = get_best_quali_relative_sector(2026, 'Japan')
#     print("Best Relative Sector in Qualifying:")
#     print(df_best_sector.to_string(index=False))