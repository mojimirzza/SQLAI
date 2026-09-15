"""
Tool: check_maintenance_window
Simple hardcoded maintenance windows.
In production, read from a config table or calendar.
"""
from datetime import datetime


# Hardcoded maintenance windows (server, day_of_week, start_hour, end_hour)
# Empty list = no maintenance windows configured
MAINTENANCE_WINDOWS = [
    # Example: {"server_sk": 1, "day": 6, "start": 2, "end": 4},  # SW01, Saturday 2-4 AM
]


def check_maintenance_window(server_sk: int | None) -> bool:
    """
    Returns True if the given server is currently in a maintenance window.
    If server_sk is None, checks if ANY server is in maintenance.
    """
    now = datetime.now()
    current_day = now.weekday()  # 0=Monday
    current_hour = now.hour

    for window in MAINTENANCE_WINDOWS:
        if window["day"] != current_day:
            continue
        if window["start"] <= current_hour < window["end"]:
            if server_sk is None or window["server_sk"] == server_sk:
                return True

    return False
