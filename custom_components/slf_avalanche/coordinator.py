"""DataUpdateCoordinator for the SLF Swiss avalanche bulletin."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .bulletin import async_get_bulletin, find_feature, region_report
from .const import (
    DOMAIN,
    IMIS_UPDATE_INTERVAL_MINUTES,
    SECTOR_URL,
    UPDATE_INTERVAL_MINUTES,
)
from .imis import async_fetch_daily_snow, async_fetch_station_measurements
from .issues import IssueReporter
from .localization import get_language

_LOGGER = logging.getLogger(__name__)

# The SLF service could not be reached, did not answer in time, answered with
# an error status or with something that is not JSON. Anything else is a bug
# in this integration and is left to surface as such.
API_ERRORS = (aiohttp.ClientError, TimeoutError, ValueError)


async def async_resolve_sector(hass: HomeAssistant, lat: float, lon: float) -> dict:
    """Determine the SLF warning region (sector) for a coordinate."""
    session = async_get_clientsession(hass)
    params = {"lat": lat, "lon": lon, "date": dt_util.now().date().isoformat()}
    async with session.get(SECTOR_URL, params=params, timeout=25) as resp:
        if resp.status == 404:
            raise UpdateFailed("No SLF warning region found for these coordinates")
        resp.raise_for_status()
        data = await resp.json(content_type=None)
    return {"sector_id": data["sector_id"], "sector_name": data["sector_name"]}


class SlfAvalancheCoordinator(DataUpdateCoordinator[dict]):
    """Fetches the sector assignment (once) and the bulletin (hourly).

    The bulletin itself is shared between all bulletin entries and read in
    Home Assistant's language (German, French, Italian or English).
    """

    def __init__(
        self,
        hass: HomeAssistant,
        latitude: float,
        longitude: float,
        name: str,
        entry_id: str | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            # The entry label in the name tells the log lines of several
            # bulletin entries apart.
            name=f"{DOMAIN} {name}",
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        self._latitude = latitude
        self._longitude = longitude
        self._sector: dict | None = None
        self.issues = IssueReporter(hass, entry_id) if entry_id else None

    async def _async_update_data(self) -> dict:
        if self._sector is None:
            try:
                self._sector = await async_resolve_sector(self.hass, self._latitude, self._longitude)
            except UpdateFailed:
                # The service knows no warning region for the coordinates:
                # that does not fix itself, say so under Repairs at once.
                if self.issues:
                    self.issues.raise_now("region_unknown")
                raise
            except API_ERRORS as err:
                if self.issues:
                    self.issues.failure("unreachable", {"host": "aws.slf.ch"})
                raise UpdateFailed(f"Could not determine the SLF warning region: {err}") from err
            if self.issues:
                self.issues.clear("region_unknown")

        try:
            bulletin = await async_get_bulletin(self.hass, get_language(self.hass))
        except API_ERRORS as err:
            if self.issues:
                self.issues.failure("unreachable", {"host": "aws.slf.ch"})
            raise UpdateFailed(f"SLF bulletin unreachable: {err}") from err
        if self.issues:
            self.issues.clear("unreachable")

        region_id = f"CH-{self._sector['sector_id']}"
        return {
            "sector_id": self._sector["sector_id"],
            "sector_name": self._sector["sector_name"],
            **region_report(find_feature(bulletin, region_id)),
        }


class ImisCoordinator(DataUpdateCoordinator[dict]):
    """Fetches the latest IMIS measurements for the selected stations.

    Data: dict keyed by station code with {"values", "dates", "fields",
    "measure_date", "new_snow_1d", "daily_snow_height", "daily_measure_date"}.
    A station that could not be fetched is absent from the dict, which is
    what its sensors use to report themselves unavailable.
    """

    def __init__(
        self, hass: HomeAssistant, stations: list[dict], name: str, entry_id: str | None = None
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_imis {name}",
            update_interval=timedelta(minutes=IMIS_UPDATE_INTERVAL_MINUTES),
        )
        self.issues = IssueReporter(hass, entry_id) if entry_id else None
        # Station metadata dicts as stored in the config entry
        # (code, label, elevation, lat, lon, type, distance_km).
        self.stations = stations
        # Stations whose last fetch failed: logged once when they fail and
        # once when they are back, not on every refresh in between.
        self._failed: set[str] = set()

    async def _fetch_station(self, code: str) -> dict | None:
        """Measurements of one station, or None when it cannot be fetched."""
        try:
            data = await async_fetch_station_measurements(self.hass, code)
        except API_ERRORS as err:
            if code in self._failed:
                _LOGGER.debug("IMIS station %s still unreachable: %s", code, err)
            else:
                _LOGGER.warning("IMIS station %s unreachable: %s", code, err)
                self._failed.add(code)
            if self.issues:
                # Six hours of failures (twelve half-hourly refreshes): the
                # station is most likely out of service, say so under Repairs.
                label = next((s.get("label") for s in self.stations if s["code"] == code), None) or code
                self.issues.failure(
                    "imis_station_unavailable", {"station": label, "code": code}, after=12, suffix=code
                )
            return None
        if code in self._failed:
            self._failed.discard(code)
            _LOGGER.info("IMIS station %s reachable again", code)
        if self.issues:
            self.issues.clear("imis_station_unavailable", suffix=code)
        return data

    async def _async_update_data(self) -> dict:
        try:
            daily = await async_fetch_daily_snow(self.hass)
        except Exception as err:  # noqa: BLE001 - daily snow is an optional extra
            _LOGGER.debug("IMIS daily-snow unavailable: %s", err)
            daily = {}

        # All stations at once rather than one after the other, so the first
        # refresh at entry setup does not wait for N sequential requests.
        fetched = await asyncio.gather(
            *(self._fetch_station(station["code"]) for station in self.stations)
        )

        result: dict[str, dict] = {}
        for station, data in zip(self.stations, fetched):
            if data is None:
                continue
            code = station["code"]
            daily_record = daily.get(code) or {}
            data["new_snow_1d"] = daily_record.get("HN_1D")
            data["daily_snow_height"] = daily_record.get("HS")
            data["daily_measure_date"] = daily_record.get("measure_date")
            result[code] = data

        if self.stations and not result:
            if self.issues:
                self.issues.failure("unreachable", {"host": "measurement-api.slf.ch"})
            raise UpdateFailed("No IMIS station reachable")
        if self.issues:
            self.issues.clear("unreachable")
        return result
