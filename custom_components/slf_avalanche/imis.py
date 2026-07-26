"""Client for the official SLF measurement API (IMIS stations).

API documentation: https://measurement-api.slf.ch/ (OpenAPI/ReDoc).
Data license: CC BY 4.0, attribution "WSL Institute for Snow and Avalanche
Research SLF" — the same attribution this integration already carries for
the avalanche bulletin.
"""
from __future__ import annotations

import math

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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


async def async_fetch_station_measurements(hass: HomeAssistant, code: str) -> dict:
    """Latest measurement record of one station plus its available fields.

    The API returns the last 24 h in 30-minute steps; the newest record can
    contain isolated nulls (sensor hiccup), so field availability is judged
    across the whole window and the newest non-null value per field is used.
    """
    session = async_get_clientsession(hass)
    async with session.get(IMIS_MEASUREMENTS_URL.format(code=code), timeout=25) as resp:
        resp.raise_for_status()
        records = await resp.json(content_type=None)

    if not isinstance(records, list) or not records:
        return {"values": {}, "fields": set(), "measure_date": None}

    values: dict[str, float] = {}
    fields: set[str] = set()
    for record in records:  # oldest -> newest; later records win
        for api_key, key in FIELD_MAP.items():
            value = record.get(api_key)
            if value is not None:
                values[key] = value
                fields.add(key)
    return {
        "values": values,
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
