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
    CONF_MODE,
    CONF_NAME,
    DOMAIN,
    MODE_BULLETIN,
    MODE_IMIS,
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


def _imis_title(stations: list[dict]) -> str:
    labels = [s["label"] for s in stations]
    shown = ", ".join(labels[:2])
    if len(labels) > 2:
        shown += f" +{len(labels) - 2}"
    return f"IMIS {shown}" if shown else "IMIS"


class SlfAvalancheConfigFlow(ConfigFlow, domain=DOMAIN):
    """Mode menu first: avalanche bulletin per location, or IMIS station favourites."""

    VERSION = 1

    def __init__(self) -> None:
        self._stations: list[dict] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return self.async_show_menu(step_id="user", menu_options=["bulletin", "imis"])

    async def async_step_bulletin(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Set up the avalanche bulletin for a location (one instance per location)."""
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
                name = user_input.get(CONF_NAME) or sector["sector_name"]
                return self.async_create_entry(
                    title=t("device_name", self.hass, name=name),
                    data={
                        CONF_MODE: MODE_BULLETIN,
                        CONF_NAME: name,
                        CONF_LATITUDE: lat,
                        CONF_LONGITUDE: lon,
                    },
                )

        schema = vol.Schema(
            {
                vol.Optional(CONF_NAME): str,
                vol.Required(CONF_LATITUDE, default=self.hass.config.latitude): vol.Coerce(float),
                vol.Required(CONF_LONGITUDE, default=self.hass.config.longitude): vol.Coerce(float),
            }
        )
        return self.async_show_form(step_id="bulletin", data_schema=schema, errors=errors)

    async def async_step_imis(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Set up favourite IMIS measuring stations (independent of a bulletin)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            stations = _selected_stations(
                self._stations, user_input.get(CONF_IMIS_STATIONS) or []
            )
            if not stations:
                errors[CONF_IMIS_STATIONS] = "no_station"
            else:
                return self.async_create_entry(
                    title=_imis_title(stations),
                    data={CONF_MODE: MODE_IMIS, CONF_IMIS_STATIONS: stations},
                )

        if not self._stations:
            try:
                stations = await async_fetch_stations(self.hass)
            except Exception:
                return self.async_abort(reason="imis_unavailable")
            self._stations = stations_by_distance(
                stations, self.hass.config.latitude, self.hass.config.longitude
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_IMIS_STATIONS, default=[]): SelectSelector(
                    SelectSelectorConfig(
                        options=_station_options(self._stations),
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="imis", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SlfAvalancheOptionsFlow()


class SlfAvalancheOptionsFlow(OptionsFlow):
    """Manage the favourite IMIS stations of an IMIS entry."""

    def __init__(self) -> None:
        self._stations: list[dict] = []

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        entry = self.config_entry
        if entry.data.get(CONF_MODE, MODE_BULLETIN) != MODE_IMIS:
            return self.async_abort(reason="no_options")

        errors: dict[str, str] = {}
        if user_input is not None:
            stations = _selected_stations(
                self._stations, user_input.get(CONF_IMIS_STATIONS) or []
            )
            if not stations:
                errors[CONF_IMIS_STATIONS] = "no_station"
            else:
                return self.async_create_entry(
                    title="", data={CONF_IMIS_STATIONS: stations}
                )

        if not self._stations:
            try:
                stations = await async_fetch_stations(self.hass)
            except Exception:
                return self.async_abort(reason="imis_unavailable")
            self._stations = stations_by_distance(
                stations, self.hass.config.latitude, self.hass.config.longitude
            )

        current = entry.options.get(
            CONF_IMIS_STATIONS, entry.data.get(CONF_IMIS_STATIONS) or []
        )
        current_codes = [s["code"] for s in current]

        schema = vol.Schema(
            {
                vol.Required(CONF_IMIS_STATIONS, default=current_codes): SelectSelector(
                    SelectSelectorConfig(
                        options=_station_options(self._stations),
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
