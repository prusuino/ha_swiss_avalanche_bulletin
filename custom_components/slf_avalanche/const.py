"""Constants for the Swiss Avalanche Bulletin (SLF) integration."""
DOMAIN = "slf_avalanche"

BULLETIN_URL = "https://aws.slf.ch/api/bulletin/caaml/de/geojson"
SECTOR_URL = "https://aws.slf.ch/api/warningregion/sector/findByLocWGS84"

UPDATE_INTERVAL_MINUTES = 60

CONF_NAME = "name"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"

# CAAML dangerRating mainValue -> EAWS 5-level danger scale (1-5). Canonical,
# language-independent — display text is looked up via localization.py.
DANGER_LEVEL_NUMBERS: dict[str, int] = {
    "low": 1,
    "moderate": 2,
    "considerable": 3,
    "high": 4,
    "very_high": 5,
}

MAX_PROBLEM_SENSORS = 3
