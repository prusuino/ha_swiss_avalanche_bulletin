"""Client for the official SLF measurement API (IMIS stations).

API documentation: https://measurement-api.slf.ch/ (OpenAPI/ReDoc).
Data license: CC BY 4.0, attribution "WSL Institute for Snow and Avalanche
Research SLF" — the same attribution this integration already carries for
the avalanche bulletin.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import IMIS_DAILY_SNOW_URL, IMIS_MEASUREMENTS_URL, IMIS_STATIONS_URL

EARTH_RADIUS_KM = 6371.0088

# Measurement fields exposed as sensors: API key -> canonical short key.
FIELD_MAP = {
    "HS": "snow_height",
    "TA_30MIN_MEAN": "air_temperature",
    "TSS_30MIN_MEAN": "snow_surface_temperature",
    "RH_30MIN_MEAN": "humidity",
    "VW_30MIN_MEAN": "wind_speed",
    "VW_30MIN_MAX": "wind_gust",
    "DW_30MIN_MEAN": "wind_direction",
}

# The measurement endpoint returns the last 24 h in 30-minute records. Only a
# value measured within this period, judged by the record's timestamp against
# the clock, counts as the current value of a field; an older one is not shown
# as live. Counting records instead would only hold while the API fills every
# missing half hour with nulls.
IMIS_CURRENT_MAX_AGE = timedelta(hours=3)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


async def async_fetch_stations(hass: HomeAssistant) -> list[dict]:
    """Fetch the IMIS station list."""
    session = async_get_clientsession(hass)
    async with session.get(IMIS_STATIONS_URL, timeout=25) as resp:
        resp.raise_for_status()
        return await resp.json(content_type=None)


def stations_by_distance(stations: list[dict], lat: float, lon: float) -> list[dict]:
    """Stations enriched with the distance to a location, nearest first."""
    result = []
    for station in stations:
        try:
            distance = haversine_km(lat, lon, float(station["lat"]), float(station["lon"]))
        except (KeyError, TypeError, ValueError):
            continue
        result.append({**station, "distance_km": round(distance, 1)})
    return sorted(result, key=lambda s: s["distance_km"])


def _measured_at(record: dict) -> datetime | None:
    """Timestamp of a measurement record as an aware UTC datetime, if usable."""
    raw = record.get("measure_date")
    if not isinstance(raw, str):
        return None
    measured = dt_util.parse_datetime(raw)
    return dt_util.as_utc(measured) if measured is not None else None


async def async_fetch_station_measurements(hass: HomeAssistant, code: str) -> dict:
    """Current measurement values of one station plus its available fields.

    The API returns the last 24 h in 30-minute steps, oldest first. The newest
    record can contain isolated nulls (sensor hiccup), so the newest non-null
    value per field measured within the last IMIS_CURRENT_MAX_AGE is used,
    together with the timestamp of the record it was taken from ("dates").
    Which fields a station measures at all ("fields", used to decide which
    sensors it gets) is judged across the whole 24 h window, so a field that
    has gone quiet keeps its sensor and reads unknown.
    """
    session = async_get_clientsession(hass)
    async with session.get(IMIS_MEASUREMENTS_URL.format(code=code), timeout=25) as resp:
        resp.raise_for_status()
        records = await resp.json(content_type=None)

    if not isinstance(records, list):
        records = []
    records = [r for r in records if isinstance(r, dict)]
    if not records:
        return {"values": {}, "dates": {}, "fields": set(), "measure_date": None}

    values: dict[str, float] = {}
    dates: dict[str, str | None] = {}
    fields: set[str] = set()
    cutoff = dt_util.utcnow() - IMIS_CURRENT_MAX_AGE
    for record in records:  # oldest -> newest; later records win
        measured = _measured_at(record)
        current = measured is not None and measured >= cutoff
        for api_key, key in FIELD_MAP.items():
            value = record.get(api_key)
            if value is None:
                continue
            fields.add(key)
            if current:
                values[key] = value
                dates[key] = record.get("measure_date")
    return {
        "values": values,
        "dates": dates,
        "fields": fields,
        "measure_date": records[-1].get("measure_date"),
    }


async def async_fetch_daily_snow(hass: HomeAssistant) -> dict[str, dict]:
    """Daily snow height and 24 h new-snow sum for all stations, by code."""
    session = async_get_clientsession(hass)
    async with session.get(IMIS_DAILY_SNOW_URL, timeout=25) as resp:
        resp.raise_for_status()
        records = await resp.json(content_type=None)
    return {
        r["station_code"]: r
        for r in records
        if isinstance(r, dict) and r.get("station_code")
    }
