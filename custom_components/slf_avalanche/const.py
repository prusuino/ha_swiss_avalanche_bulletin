"""Constants for the Swiss Avalanche Bulletin (SLF) integration."""
DOMAIN = "slf_avalanche"

BULLETIN_URL = "https://aws.slf.ch/api/bulletin/caaml/de/geojson"
SECTOR_URL = "https://aws.slf.ch/api/warningregion/sector/findByLocWGS84"

# Official SLF measurement API (https://measurement-api.slf.ch/, CC BY 4.0).
IMIS_STATIONS_URL = "https://measurement-api.slf.ch/public/api/imis/stations"
IMIS_MEASUREMENTS_URL = "https://measurement-api.slf.ch/public/api/imis/station/{code}/measurements"
IMIS_DAILY_SNOW_URL = "https://measurement-api.slf.ch/public/api/imis/daily-snow"

UPDATE_INTERVAL_MINUTES = 60
IMIS_UPDATE_INTERVAL_MINUTES = 30

CONF_NAME = "name"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_IMIS_STATIONS = "imis_stations"

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
