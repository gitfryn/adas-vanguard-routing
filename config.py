# config.py
# Constants and default configurations for the ADAS Routing Engine

TAMPA_LAT = 27.9506
TAMPA_LON = -82.4572

DEPOT_LAT = 28.0543
DEPOT_LON = -82.4597

DRIVE_TIME_OPTIONS = {
    "30 Minutes": 30,
    "1 Hour": 60,
    "2 Hours": 120,
    "4 Hours": 240
}

# Average ADAS collection speed in Tampa (30 mph) -> meters/second
AVERAGE_SPEED_MPS = 13.4 

# Base line complexity
BASE_COMPLEXITY = 20
