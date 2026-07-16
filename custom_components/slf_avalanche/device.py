"""Shared device info for all platforms."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import CONF_NAME, DOMAIN
from .localization import t


def device_info(hass: HomeAssistant, entry: ConfigEntry) -> DeviceInfo:
    name = entry.data.get(CONF_NAME) or entry.title
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=t("device_name", hass, name=name),
        manufacturer=t("manufacturer", hass),
        model=t("model", hass),
        entry_type="service",
    )
