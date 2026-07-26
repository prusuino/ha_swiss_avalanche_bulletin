"""DataUpdateCoordinator for the SLF Swiss avalanche bulletin."""
from __future__ import annotations

import logging
from datetime import date, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    BULLETIN_URL,
    DANGER_LEVEL_NUMBERS,
    DOMAIN,
    IMIS_UPDATE_INTERVAL_MINUTES,
    SECTOR_URL,
    UPDATE_INTERVAL_MINUTES,
)
from .imis import async_fetch_daily_snow, async_fetch_station_measurements

_LOGGER = logging.getLogger(__name__)


async def async_resolve_sector(hass: HomeAssistant, lat: float, lon: float) -> dict:
    """Determine the SLF warning region (sector) for a coordinate."""
    session = async_get_clientsession(hass)
    params = {"lat": lat, "lon": lon, "date": date.today().isoformat()}
    async with session.get(SECTOR_URL, params=params, timeout=25) as resp:
        if resp.status == 404:
            raise UpdateFailed("No SLF warning region found for these coordinates")
        resp.raise_for_status()
        data = await resp.json(content_type=None)
    return {"sector_id": data["sector_id"], "sector_name": data["sector_name"]}


async def async_fetch_bulletin(hass: HomeAssistant) -> dict:
    """Fetch the currently valid avalanche bulletin (empty outside winter season)."""
    session = async_get_clientsession(hass)
    async with session.get(BULLETIN_URL, timeout=25) as resp:
        resp.raise_for_status()
        return await resp.json(content_type=None)


def _find_feature_for_region(bulletin: dict, region_id: str) -> dict | None:
    for feature in bulletin.get("features", []):
        regions = feature.get("properties", {}).get("regions", [])
        if any(r.get("regionID") == region_id for r in regions):
            return feature
    return None


def _worst_danger_rating(danger_ratings: list[dict]) -> dict | None:
    """Pick the highest reported danger level (if split by elevation)."""
    best = None
    best_level = -1
    for dr in danger_ratings:
        level = DANGER_LEVEL_NUMBERS.get(dr.get("mainValue", ""), 0)
        if level > best_level:
            best_level = level
            best = dr
    return best


class SlfAvalancheCoordinator(DataUpdateCoordinator[dict]):
    """Fetches the sector assignment (once) and the bulletin (hourly)."""

    def __init__(self, hass: HomeAssistant, latitude: float, longitude: float) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        self._latitude = latitude
        self._longitude = longitude
        self._sector: dict | None = None

    async def _async_update_data(self) -> dict:
        if self._sector is None:
            try:
                self._sector = await async_resolve_sector(self.hass, self._latitude, self._longitude)
            except UpdateFailed:
                raise
            except Exception as err:
                raise UpdateFailed(f"Could not determine the SLF warning region: {err}") from err

        try:
            bulletin = await async_fetch_bulletin(self.hass)
        except Exception as err:
            raise UpdateFailed(f"SLF bulletin unreachable: {err}") from err

        region_id = f"CH-{self._sector['sector_id']}"
        feature = _find_feature_for_region(bulletin, region_id)

        result = {
            "sector_id": self._sector["sector_id"],
            "sector_name": self._sector["sector_name"],
            "active": feature is not None,
        }

        if feature is None:
            return result

        props = feature.get("properties", {})
        danger_ratings = props.get("dangerRatings", [])
        worst = _worst_danger_rating(danger_ratings)
        main_value = (worst or {}).get("mainValue")

        result.update(
            {
                "danger_level": DANGER_LEVEL_NUMBERS.get(main_value or "", None),
                "danger_main_value": main_value,
                "danger_ratings_raw": danger_ratings,
                "valid_from": props.get("validTime", {}).get("startTime"),
                "valid_to": props.get("validTime", {}).get("endTime"),
                "next_update": props.get("nextUpdate"),
                "publication_time": props.get("publicationTime"),
                "unscheduled": props.get("unscheduled"),
                "avalanche_problems": props.get("avalancheProblems", []),
            }
        )
        return result


class ImisCoordinator(DataUpdateCoordinator[dict]):
    """Fetches the latest IMIS measurements for the selected stations.

    Data: dict keyed by station code with {"values", "fields", "measure_date",
    "new_snow_1d", "daily_snow_height"}.
    """

    def __init__(self, hass: HomeAssistant, stations: list[dict]) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_imis",
            update_interval=timedelta(minutes=IMIS_UPDATE_INTERVAL_MINUTES),
        )
        # Station metadata dicts as stored in the config entry
        # (code, label, elevation, lat, lon, type, distance_km).
        self.stations = stations

    async def _async_update_data(self) -> dict:
        try:
            daily = await async_fetch_daily_snow(self.hass)
        except Exception as err:  # noqa: BLE001 - daily snow is an optional extra
            _LOGGER.debug("IMIS daily-snow unavailable: %s", err)
            daily = {}

        result: dict[str, dict] = {}
        errors = 0
        for station in self.stations:
            code = station["code"]
            try:
                data = await async_fetch_station_measurements(self.hass, code)
            except Exception as err:
                _LOGGER.warning("IMIS station %s unreachable: %s", code, err)
                errors += 1
                continue
            daily_record = daily.get(code) or {}
            data["new_snow_1d"] = daily_record.get("HN_1D")
            data["daily_snow_height"] = daily_record.get("HS")
            result[code] = data

        if errors and not result:
            raise UpdateFailed("No IMIS station reachable")
        return result
