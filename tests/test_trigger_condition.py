"""The triggers and conditions for the automation editor, tried with real
automations while the bulletin of a location changes - also across the
times without a level: outside the season and while the SLF is unreachable."""
from __future__ import annotations

from unittest.mock import patch

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.slf_avalanche import condition, trigger
from custom_components.slf_avalanche.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_MODE, CONF_NAME, DOMAIN, MODE_BULLETIN

COORD = "custom_components.slf_avalanche.coordinator."
FOREIGN = "sensor.cellar_humidity"


class Bulletin:
    """The faked bulletin of one region: set `level` (None = no rating) or `error`."""

    def __init__(self) -> None:
        self.level: str | None = None
        self.error: Exception | None = None

    async def get(self, hass, language):
        if self.error:
            raise self.error
        props: dict = {"regions": [{"regionID": "CH-5123", "name": "Davos"}]}
        if self.level:
            props["dangerRatings"] = [{"mainValue": self.level}]
            props["validTime"] = {"startTime": "2026-11-23T16:00:00Z", "endTime": "2026-11-24T16:00:00Z"}
        return {"features": [{"properties": props}]}


async def _setup(hass: HomeAssistant, bulletin: Bulletin):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="46.8_9.83", title="Tour",
                            data={CONF_MODE: MODE_BULLETIN, CONF_NAME: "Tour", CONF_LATITUDE: 46.8, CONF_LONGITUDE: 9.83})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    danger = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_danger_level")
    return entry, danger


async def _play(hass: HomeAssistant, entry, bulletin: Bulletin, level: str | None, error: Exception | None = None) -> None:
    bulletin.level, bulletin.error = level, error
    await entry.runtime_data.bulletin.async_refresh()
    await hass.async_block_till_done()


async def _automation(hass: HomeAssistant, *, trigger: dict | None = None, condition: dict | None = None) -> list:
    calls = async_mock_service(hass, "test", "automation")
    config = {"alias": "Tell me", "trigger": trigger or {"trigger": "event", "event_type": "check_now"}, "action": {"action": "test.automation"}}
    if condition:
        config["condition"] = condition
    assert await async_setup_component(hass, "automation", {"automation": config})
    await hass.async_block_till_done()
    assert hass.states.get("automation.tell_me") is not None, "the automation was rejected"
    return calls


async def _check(hass: HomeAssistant, calls: list) -> bool:
    before = len(calls)
    hass.bus.async_fire("check_now")
    await hass.async_block_till_done()
    return len(calls) > before


def _patched(bulletin: Bulletin):
    return (
        patch(COORD + "async_resolve_sector", return_value={"sector_id": "5123", "sector_name": "Davos"}),
        patch(COORD + "async_get_bulletin", side_effect=bulletin.get),
    )


async def test_platforms_offer_their_triggers_and_conditions(hass: HomeAssistant) -> None:
    assert set(await trigger.async_get_triggers(hass)) == {"danger_level_reached", "danger_level_changed"}
    assert await condition.async_get_conditions(hass)


async def test_level_reached_from_a_lower_level_and_from_no_level(hass: HomeAssistant, enable_custom_integrations) -> None:
    bulletin = Bulletin()
    a, b = _patched(bulletin)
    with a, b:
        entry, danger = await _setup(hass, bulletin)  # outside the season: no level
        assert hass.states.get(danger).state == "unknown"
        hass.states.async_set(FOREIGN, "1")
        calls = await _automation(hass, trigger={"trigger": "slf_avalanche.danger_level_reached",
                                                 "target": {"entity_id": [danger, FOREIGN]}, "options": {"minimum_level": 3}})
        hass.states.async_set(FOREIGN, "4")  # not ours
        await hass.async_block_till_done()
        assert len(calls) == 0

        await _play(hass, entry, bulletin, "considerable")  # the first bulletin of the season starts at 3
        assert len(calls) == 1
        await _play(hass, entry, bulletin, "high")  # already above
        assert len(calls) == 1
        await _play(hass, entry, bulletin, "moderate")
        await _play(hass, entry, bulletin, "considerable")
        assert len(calls) == 2

        # the SLF is unreachable for a while and the level is unchanged afterwards
        await _play(hass, entry, bulletin, "considerable", aiohttp.ClientError("down"))
        assert hass.states.get(danger).state == "unavailable"
        await _play(hass, entry, bulletin, "considerable")
        assert len(calls) == 2
        # it rose during an outage
        await _play(hass, entry, bulletin, "moderate")
        await _play(hass, entry, bulletin, "moderate", aiohttp.ClientError("down"))
        await _play(hass, entry, bulletin, "high")
        assert len(calls) == 3
        # the region loses its rating and gets it back at the same level
        await _play(hass, entry, bulletin, None)
        await _play(hass, entry, bulletin, "high")
        assert len(calls) == 3


async def test_level_changed(hass: HomeAssistant, enable_custom_integrations) -> None:
    bulletin = Bulletin()
    a, b = _patched(bulletin)
    with a, b:
        entry, danger = await _setup(hass, bulletin)
        calls = await _automation(hass, trigger={"trigger": "slf_avalanche.danger_level_changed", "target": {"entity_id": danger}})
        await _play(hass, entry, bulletin, "moderate")  # the first level after none
        assert len(calls) == 1
        await _play(hass, entry, bulletin, "considerable")
        assert len(calls) == 2
        await _play(hass, entry, bulletin, "considerable", aiohttp.ClientError("down"))
        await _play(hass, entry, bulletin, "considerable")  # back unchanged
        assert len(calls) == 2
        await _play(hass, entry, bulletin, None)
        await _play(hass, entry, bulletin, "low")  # back with another level
        assert len(calls) == 3


async def test_conditions(hass: HomeAssistant, enable_custom_integrations) -> None:
    bulletin = Bulletin()
    bulletin.level = "considerable"
    a, b = _patched(bulletin)
    with a, b:
        entry, danger = await _setup(hass, bulletin)
        names = list(await condition.async_get_conditions(hass))
        at_least = next(n for n in names if "least" in n)
        hass.states.async_set(FOREIGN, "5")
        calls = await _automation(hass, condition={"condition": f"slf_avalanche.{at_least}", "target": {"entity_id": [danger, FOREIGN]}, "options": {"level": 4}})
        assert await _check(hass, calls) is False  # 3 is below 4; the foreign 5 does not count
        await _play(hass, entry, bulletin, "high")
        assert await _check(hass, calls) is True
        await _play(hass, entry, bulletin, None)
        assert await _check(hass, calls) is False
