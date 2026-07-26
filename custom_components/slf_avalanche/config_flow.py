"""Config flow for the Swiss Avalanche Bulletin (SLF) integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_IMIS_STATIONS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    DOMAIN,
)
from .coordinator import async_resolve_sector
from .imis import async_fetch_stations, stations_by_distance
from .localization import t

# Station type markers shown in the picker.
_TYPE_LABEL = {
    "SNOW_FLAT": "❄",
    "SNOW_SLOPE": "❄⛰",
    "WIND": "🌬",
    "FLOWCAPT": "🌬❄",
}


def _station_options(stations: list[dict]) -> list[SelectOptionDict]:
    """Selector options for all stations, nearest first, searchable by name."""
    return [
        SelectOptionDict(
            value=s["code"],
            label=(
                f"{s.get('label') or s['code']} "
                f"({s['code']}, {round(s.get('elevation') or 0)} m, "
                f"{s['distance_km']} km) {_TYPE_LABEL.get(s.get('type'), '')}"
            ),
        )
        for s in stations
    ]


def _selected_stations(stations: list[dict], codes: list[str]) -> list[dict]:
    """Compact metadata of the selected stations for storage in the entry."""
    by_code = {s["code"]: s for s in stations}
    result = []
    for code in codes:
        s = by_code.get(code)
        if s is None:
            continue
        result.append(
            {
                "code": s["code"],
                "label": s.get("label") or s["code"],
                "elevation": s.get("elevation"),
                "lat": s.get("lat"),
                "lon": s.get("lon"),
                "type": s.get("type"),
                "distance_km": s.get("distance_km"),
            }
        )
    return result


class SlfAvalancheConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow: pick a location (defaults to the HA home location), one instance per location."""

    VERSION = 1

    def __init__(self) -> None:
        self._location: dict[str, Any] = {}
        self._stations: list[dict] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            lat = user_input[CONF_LATITUDE]
            lon = user_input[CONF_LONGITUDE]
            unique_id = f"{round(lat, 3)}_{round(lon, 3)}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            try:
                sector = await async_resolve_sector(self.hass, lat, lon)
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                self._location = {
                    CONF_NAME: user_input.get(CONF_NAME) or sector["sector_name"],
                    CONF_LATITUDE: lat,
                    CONF_LONGITUDE: lon,
                }
                return await self.async_step_imis()

        default_lat = self.hass.config.latitude
        default_lon = self.hass.config.longitude

        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME): str,
                vol.Required(CONF_LATITUDE, default=default_lat): vol.Coerce(float),
                vol.Required(CONF_LONGITUDE, default=default_lon): vol.Coerce(float),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_imis(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Optionally select favourite IMIS measuring stations (any, not just nearby)."""
        if user_input is not None:
            stations = _selected_stations(
                self._stations, user_input.get(CONF_IMIS_STATIONS) or []
            )
            return self.async_create_entry(
                title=t("device_name", self.hass, name=self._location[CONF_NAME]),
                data={**self._location, CONF_IMIS_STATIONS: stations},
            )

        try:
            stations = await async_fetch_stations(self.hass)
        except Exception:
            # The measurement API being down must not block the bulletin setup.
            return self.async_create_entry(
                title=t("device_name", self.hass, name=self._location[CONF_NAME]),
                data={**self._location, CONF_IMIS_STATIONS: []},
            )

        self._stations = stations_by_distance(
            stations, self._location[CONF_LATITUDE], self._location[CONF_LONGITUDE]
        )

        schema = vol.Schema(
            {
                vol.Optional(CONF_IMIS_STATIONS, default=[]): SelectSelector(
                    SelectSelectorConfig(
                        options=_station_options(self._stations),
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="imis", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SlfAvalancheOptionsFlow()


class SlfAvalancheOptionsFlow(OptionsFlow):
    """Manage the favourite IMIS stations of an existing location entry."""

    def __init__(self) -> None:
        self._stations: list[dict] = []

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            stations = _selected_stations(
                self._stations, user_input.get(CONF_IMIS_STATIONS) or []
            )
            return self.async_create_entry(title="", data={CONF_IMIS_STATIONS: stations})

        try:
            stations = await async_fetch_stations(self.hass)
        except Exception:
            errors["base"] = "cannot_connect"
            return self.async_show_form(step_id="init", errors=errors)

        entry = self.config_entry
        self._stations = stations_by_distance(
            stations, entry.data[CONF_LATITUDE], entry.data[CONF_LONGITUDE]
        )
        current = entry.options.get(
            CONF_IMIS_STATIONS, entry.data.get(CONF_IMIS_STATIONS) or []
        )
        current_codes = [s["code"] for s in current]

        schema = vol.Schema(
            {
                vol.Optional(CONF_IMIS_STATIONS, default=current_codes): SelectSelector(
                    SelectSelectorConfig(
                        options=_station_options(self._stations),
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
