"""Config flow for the Swiss Avalanche Bulletin (SLF) integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, DOMAIN
from .coordinator import async_resolve_sector
from .localization import t


class SlfAvalancheConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow: pick a location (defaults to the HA home location), one instance per location."""

    VERSION = 1

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
                name = user_input.get(CONF_NAME) or sector["sector_name"]
                return self.async_create_entry(
                    title=t("device_name", self.hass, name=name),
                    data={
                        CONF_NAME: name,
                        CONF_LATITUDE: lat,
                        CONF_LONGITUDE: lon,
                    },
                )

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
