"""Config flow for the Swiss Avalanche Bulletin (SLF) integration.

Setup starts with a menu: the avalanche bulletin for a location, or
favourite IMIS measuring stations. Reconfigure (the entry's menu under
Settings → Devices & services) changes an entry in place with the form of
its own mode: another location or label for a bulletin, other stations for
an IMIS entry. The entry keeps its id, so its entities keep their ids and
history; the devices of stations that are no longer selected are removed on
the reload, as they are after a change in the options.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.helpers.update_coordinator import UpdateFailed

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
from .coordinator import API_ERRORS, async_resolve_sector
from .imis import async_fetch_stations, stations_by_distance
from .localization import t

_LOGGER = logging.getLogger(__name__)

# Shown as "cannot connect": the service is unreachable, or (UpdateFailed) it
# knows no warning region for the coordinates.
_CANNOT_CONNECT = (UpdateFailed, *API_ERRORS)

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


def _stations_configured_elsewhere(
    hass: HomeAssistant, exclude_entry_id: str | None = None
) -> set[str]:
    """Codes of the stations that are already favourites of another IMIS entry."""
    codes: set[str] = set()
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == exclude_entry_id:
            continue
        if entry.data.get(CONF_MODE, MODE_BULLETIN) != MODE_IMIS:
            continue
        stations = entry.options.get(
            CONF_IMIS_STATIONS, entry.data.get(CONF_IMIS_STATIONS) or []
        )
        codes.update(s["code"] for s in stations)
    return codes


def _imis_title(stations: list[dict]) -> str:
    labels = [s["label"] for s in stations]
    shown = ", ".join(labels[:2])
    if len(labels) > 2:
        shown += f" +{len(labels) - 2}"
    return f"IMIS {shown}" if shown else "IMIS"


def _current_stations(entry: ConfigEntry) -> list[dict]:
    """The entry's favourite stations: the options win over the data."""
    return entry.options.get(CONF_IMIS_STATIONS, entry.data.get(CONF_IMIS_STATIONS) or [])


def _bulletin_schema(defaults: dict[str, Any]) -> vol.Schema:
    name_key = (
        vol.Optional(CONF_NAME, default=defaults[CONF_NAME])
        if defaults.get(CONF_NAME)
        else vol.Optional(CONF_NAME)
    )
    return vol.Schema(
        {
            name_key: str,
            vol.Required(CONF_LATITUDE, default=defaults[CONF_LATITUDE]): vol.Coerce(float),
            vol.Required(CONF_LONGITUDE, default=defaults[CONF_LONGITUDE]): vol.Coerce(float),
        }
    )


def _imis_schema(stations: list[dict], current_codes: list[str]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_IMIS_STATIONS, default=current_codes): SelectSelector(
                SelectSelectorConfig(
                    options=_station_options(stations),
                    multiple=True,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


class SlfAvalancheConfigFlow(ConfigFlow, domain=DOMAIN):
    """Mode menu first: avalanche bulletin per location, or IMIS station favourites."""

    VERSION = 1

    def __init__(self) -> None:
        self._stations: list[dict] = []

    async def _async_station_list(self) -> list[dict] | None:
        """Every IMIS station sorted by distance from home, fetched once per
        flow; None when the list could not be read."""
        if not self._stations:
            try:
                stations = await async_fetch_stations(self.hass)
            except API_ERRORS:
                return None
            self._stations = stations_by_distance(
                stations, self.hass.config.latitude, self.hass.config.longitude
            )
        return self._stations

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["bulletin", "imis"])

    # ---------------------------------------------------------- bulletin

    async def async_step_bulletin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up the avalanche bulletin for a location (one instance per location)."""
        return await self._async_bulletin_form("bulletin", user_input, None)

    async def async_step_reconfigure_bulletin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_bulletin_form(
            "reconfigure_bulletin", user_input, self._get_reconfigure_entry()
        )

    async def _async_bulletin_form(
        self, step_id: str, user_input: dict[str, Any] | None, entry: ConfigEntry | None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            lat = user_input[CONF_LATITUDE]
            lon = user_input[CONF_LONGITUDE]
            unique_id = f"{round(lat, 3)}_{round(lon, 3)}"
            await self.async_set_unique_id(unique_id)
            if entry is None or unique_id != entry.unique_id:
                self._abort_if_unique_id_configured()

            try:
                sector = await async_resolve_sector(self.hass, lat, lon)
            except _CANNOT_CONNECT:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - shown as "unknown", logged for the bug report
                _LOGGER.exception("Unexpected error while resolving the SLF warning region")
                errors["base"] = "unknown"
            else:
                name = (user_input.get(CONF_NAME) or "").strip() or sector["sector_name"]
                title = t("device_name", self.hass, name=name)
                data = {
                    CONF_MODE: MODE_BULLETIN,
                    CONF_NAME: name,
                    CONF_LATITUDE: lat,
                    CONF_LONGITUDE: lon,
                }
                if entry is None:
                    return self.async_create_entry(title=title, data=data)
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=unique_id,
                    title=title,
                    data=data,
                    reason="reconfigure_successful",
                )

        defaults = {
            CONF_NAME: entry.data.get(CONF_NAME, "") if entry else "",
            CONF_LATITUDE: entry.data.get(CONF_LATITUDE, self.hass.config.latitude)
            if entry
            else self.hass.config.latitude,
            CONF_LONGITUDE: entry.data.get(CONF_LONGITUDE, self.hass.config.longitude)
            if entry
            else self.hass.config.longitude,
        }
        schema = _bulletin_schema(defaults)
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

    # -------------------------------------------------------------- imis

    async def async_step_imis(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Set up favourite IMIS measuring stations (independent of a bulletin)."""
        return await self._async_imis_form("imis", user_input, None)

    async def async_step_reconfigure_imis(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_imis_form(
            "reconfigure_imis", user_input, self._get_reconfigure_entry()
        )

    async def _async_imis_form(
        self, step_id: str, user_input: dict[str, Any] | None, entry: ConfigEntry | None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            stations = _selected_stations(
                self._stations, user_input.get(CONF_IMIS_STATIONS) or []
            )
            taken = _stations_configured_elsewhere(
                self.hass, entry.entry_id if entry else None
            )
            if not stations:
                errors[CONF_IMIS_STATIONS] = "no_station"
            elif any(s["code"] in taken for s in stations):
                errors[CONF_IMIS_STATIONS] = "station_already_configured"
            else:
                data = {CONF_MODE: MODE_IMIS, CONF_IMIS_STATIONS: stations}
                if entry is None:
                    return self.async_create_entry(title=_imis_title(stations), data=data)
                # The new selection goes to the data; an older selection in
                # the options would win over it, so it is dropped.
                return self.async_update_reload_and_abort(
                    entry,
                    title=_imis_title(stations),
                    data=data,
                    options={
                        k: v for k, v in entry.options.items() if k != CONF_IMIS_STATIONS
                    },
                    reason="reconfigure_successful",
                )

        stations = await self._async_station_list()
        if stations is None:
            return self.async_abort(reason="imis_unavailable")

        current_codes = [s["code"] for s in _current_stations(entry)] if entry else []
        return self.async_show_form(
            step_id=step_id, data_schema=_imis_schema(stations, current_codes), errors=errors
        )

    # ------------------------------------------------------- reconfigure

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change an entry with the form of its own mode."""
        entry = self._get_reconfigure_entry()
        if entry.data.get(CONF_MODE, MODE_BULLETIN) == MODE_IMIS:
            return await self.async_step_reconfigure_imis(user_input)
        return await self.async_step_reconfigure_bulletin(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SlfAvalancheOptionsFlow()


class SlfAvalancheOptionsFlow(OptionsFlow):
    """Manage the favourite IMIS stations of an IMIS entry."""

    def __init__(self) -> None:
        self._stations: list[dict] = []

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self.config_entry
        if entry.data.get(CONF_MODE, MODE_BULLETIN) != MODE_IMIS:
            return self.async_abort(reason="no_options")

        errors: dict[str, str] = {}
        if user_input is not None:
            stations = _selected_stations(
                self._stations, user_input.get(CONF_IMIS_STATIONS) or []
            )
            taken = _stations_configured_elsewhere(self.hass, entry.entry_id)
            if not stations:
                errors[CONF_IMIS_STATIONS] = "no_station"
            elif any(s["code"] in taken for s in stations):
                errors[CONF_IMIS_STATIONS] = "station_already_configured"
            else:
                return self.async_create_entry(
                    title="", data={CONF_IMIS_STATIONS: stations}
                )

        if not self._stations:
            try:
                stations = await async_fetch_stations(self.hass)
            except API_ERRORS:
                return self.async_abort(reason="imis_unavailable")
            except Exception:  # noqa: BLE001 - shown as "unknown", logged for the bug report
                _LOGGER.exception("Unexpected error while fetching the IMIS station list")
                return self.async_abort(reason="unknown")
            self._stations = stations_by_distance(
                stations, self.hass.config.latitude, self.hass.config.longitude
            )

        current_codes = [s["code"] for s in _current_stations(entry)]
        return self.async_show_form(
            step_id="init",
            data_schema=_imis_schema(self._stations, current_codes),
            errors=errors,
        )
