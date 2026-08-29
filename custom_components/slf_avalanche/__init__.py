"""Swiss Avalanche Bulletin (SLF) integration."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_IMIS_STATIONS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    DOMAIN,
    MODE_BULLETIN,
    MODE_IMIS,
    STATIC_URL_BASE,
)
from .coordinator import ImisCoordinator, SlfAvalancheCoordinator

PLATFORMS = ["sensor"]


class RuntimeData:
    """Per-entry runtime data: bulletin coordinator and/or IMIS coordinator."""

    def __init__(
        self,
        bulletin: SlfAvalancheCoordinator | None,
        imis: ImisCoordinator | None,
    ) -> None:
        self.bulletin = bulletin
        self.imis = imis


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not hass.data.get(f"{DOMAIN}_static_registered"):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    STATIC_URL_BASE,
                    str(Path(__file__).parent / "static"),
                    cache_headers=True,
                )
            ]
        )
        hass.data[f"{DOMAIN}_static_registered"] = True

    mode = entry.data.get(CONF_MODE, MODE_BULLETIN)

    bulletin = None
    if mode == MODE_BULLETIN:
        bulletin = SlfAvalancheCoordinator(
            hass, entry.data[CONF_LATITUDE], entry.data[CONF_LONGITUDE]
        )
        await bulletin.async_config_entry_first_refresh()

    imis = None
    stations = entry.options.get(
        CONF_IMIS_STATIONS, entry.data.get(CONF_IMIS_STATIONS) or []
    )
    if mode == MODE_IMIS and stations:
        imis = ImisCoordinator(hass, stations)
        await imis.async_config_entry_first_refresh()

    _cleanup_stale_station_devices(hass, entry, stations)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = RuntimeData(bulletin, imis)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
        # Favourite stations changed -> rebuild coordinators and entities.
        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_options_updated))
    return True


def _cleanup_stale_station_devices(
    hass: HomeAssistant, entry: ConfigEntry, stations: list[dict]
) -> None:
    """Remove devices of stations that are no longer selected as favourites."""
    keep = {f"{entry.entry_id}_imis_{s['code']}" for s in stations}
    registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        for domain, identifier in device.identifiers:
            if (
                domain == DOMAIN
                and identifier.startswith(f"{entry.entry_id}_imis_")
                and identifier not in keep
            ):
                registry.async_remove_device(device.id)
                break


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
