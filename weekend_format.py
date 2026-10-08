"""Race-weekend format detection (dependency-free so it can be unit-tested)."""
from __future__ import annotations


def is_sprint_weekend(event, legacy: bool = False) -> bool:
    """True if the event has a sprint race.

    Sprint weekends are laid out differently by era (FastF1 session names):
      2022:       Practice 1, Qualifying, Practice 2, Sprint,           Race   -> Sprint is session 4
      2023:       Practice 1, Qualifying, Sprint Shootout, Sprint,      Race   -> Sprint is session 4
      2024+:      Practice 1, Sprint Qualifying, Sprint, Qualifying,    Race   -> Sprint is session 3
    The original check (`get_session_name(4) == "Sprint"`, kept as legacy=True so past results stay
    reproducible) therefore only matched 2022-2023, and silently treated every 2024+ sprint weekend
    as a standard weekend. The fixed check looks for "Sprint" in any session name.
    """
    if legacy:
        return event.get_session_name(4) == "Sprint"
    for i in range(1, 6):
        try:
            if "sprint" in str(event.get_session_name(i)).lower():
                return True
        except Exception:
            continue
    return False
