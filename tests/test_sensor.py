"""The bulletin sensors of one location, set up end to end with the SLF
service patched: today's level, tomorrow's, the trend and the weather."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.slf_avalanche.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_MODE, CONF_NAME, DOMAIN, MODE_BULLETIN

from .test_bulletin import UNRATED
from .test_bulletin_swiss import SWISS

COORD = "custom_components.slf_avalanche.coordinator."


async def _setup(hass: HomeAssistant, bulletin: dict, region: str) -> MockConfigEntry:
    hass.config.language = "de"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_MODE: MODE_BULLETIN, CONF_NAME: "Tour", CONF_LATITUDE: 46.8, CONF_LONGITUDE: 9.83},
        title="Tour",
        unique_id="46.8_9.83",
    )
    entry.add_to_hass(hass)
    with (
        patch(COORD + "async_resolve_sector", return_value={"sector_id": region, "sector_name": "Davos"}),
        patch(COORD + "async_get_bulletin", return_value=bulletin) as fetch,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert fetch.call_args.args[1] == "de"  # the bulletin in Home Assistant's language
    return entry


def _id(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> str:
    return er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_{key}")


async def test_rated_location(hass: HomeAssistant, enable_custom_integrations) -> None:
    entry = await _setup(hass, {"features": [SWISS]}, "5123")
    level = hass.states.get(_id(hass, entry, "danger_level"))
    assert level.state == "3"
    assert level.attributes["danger_level_detail"] == "3="
    assert level.attributes["active"] is True

    tomorrow = hass.states.get(_id(hass, entry, "danger_level_tomorrow"))
    assert tomorrow.state == "3"
    assert tomorrow.attributes["danger_level_detail"] == "3-"
    assert tomorrow.attributes["danger_text"] == "Erheblich"

    trend = hass.states.get(_id(hass, entry, "trend"))
    assert trend.state == "Abnehmend"
    assert trend.attributes["trend"] == "decreasing"

    snow = hass.states.get(_id(hass, entry, "new_snow_forecast"))
    assert snow.state == "6"
    assert snow.attributes["unit_of_measurement"] == "cm"
    assert hass.states.get(_id(hass, entry, "new_snow_last_24h")).state == "16"
    limit = hass.states.get(_id(hass, entry, "snowfall_limit"))
    assert limit.state == "unknown"
    assert limit.attributes["below_region"] is True

    # wind and temperature exist but are disabled by default
    registry = er.async_get(hass)
    for key in ("wind_forecast", "temperature_forecast"):
        assert registry.async_get(_id(hass, entry, key)).disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_unrated_location_reports_nothing(hass: HomeAssistant, enable_custom_integrations) -> None:
    entry = await _setup(hass, {"features": [UNRATED]}, "8226")
    level = hass.states.get(_id(hass, entry, "danger_level"))
    assert level.state == "unknown"
    assert level.attributes["active"] is False
    for key in ("danger_level_tomorrow", "trend", "new_snow_forecast", "snowfall_limit"):
        state = hass.states.get(_id(hass, entry, key))
        assert state.state == "unknown"
        assert "trend" not in state.attributes
