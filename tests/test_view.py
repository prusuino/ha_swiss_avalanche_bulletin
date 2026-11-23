"""The data the bundled cards read: GET /api/slf_avalanche/bulletin."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.slf_avalanche.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_MODE, CONF_NAME, DOMAIN, MODE_BULLETIN
from custom_components.slf_avalanche.view import map_regions

from .test_bulletin import UNRATED
from .test_bulletin_swiss import SWISS

GEOMETRY = {"type": "Polygon", "coordinates": [[[9.812345678, 46.8], [9.9, 46.8], [9.9, 46.9], [9.812345678, 46.8]]]}
BULLETIN = {"features": [{**SWISS, "geometry": GEOMETRY}, {**UNRATED, "geometry": {"type": "MultiPolygon", "coordinates": [GEOMETRY["coordinates"]]}}]}


def test_map_regions():
    regions = map_regions(BULLETIN, "fr")
    assert regions[0]["ids"] == ["CH-5123"]
    assert regions[0]["name"] == "Davos"
    assert regions[0]["level"] == 3
    assert regions[0]["detail"] == "3="
    assert regions[0]["text"] == "Marqué"
    assert regions[0]["polygons"][0][0][0] == [9.8123, 46.8]  # rounded to about 10 m
    assert regions[1]["level"] is None  # listed without a rating
    assert len(regions[1]["polygons"]) == 1
    assert map_regions({"features": [{"properties": {}, "geometry": None}]}, "de")[0]["polygons"] == []


async def test_view_answers_with_map_and_locations(hass: HomeAssistant, hass_client, enable_custom_integrations) -> None:
    hass.config.language = "de"
    assert await async_setup_component(hass, "http", {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_MODE: MODE_BULLETIN, CONF_NAME: "Tour", CONF_LATITUDE: 46.8, CONF_LONGITUDE: 9.83},
        title="Tour",
        unique_id="46.8_9.83",
    )
    entry.add_to_hass(hass)
    with (
        patch("custom_components.slf_avalanche.coordinator.async_resolve_sector", return_value={"sector_id": "5123", "sector_name": "Davos"}),
        patch("custom_components.slf_avalanche.coordinator.async_get_bulletin", return_value=BULLETIN),
        patch("custom_components.slf_avalanche.view.async_get_bulletin", return_value=BULLETIN) as fetch,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        client = await hass_client()
        response = await client.get("/api/slf_avalanche/bulletin?lang=it")
        assert response.status == 200
        data = await response.json()
        assert fetch.call_args.args[1] == "it"

        response = await client.get("/api/slf_avalanche/bulletin?lang=xx")
        assert (await response.json())["language"] == "en"

    assert data["language"] == "it"
    assert data["season"] is True
    assert len(data["regions"]) == 2
    location = data["locations"][0]
    assert location["name"] == "Tour"
    assert location["region_id"] == "CH-5123"
    assert location["danger_text"] == "Marcato"
    assert location["danger_level_detail"] == "3="
    assert location["trend"] == "decreasing"
    assert location["new_snow_forecast"]["by_elevation"] == {"1500": 4, "2500": 6}
    assert "danger_ratings_raw" not in location


async def test_view_reports_an_unreachable_service(hass: HomeAssistant, hass_client, enable_custom_integrations) -> None:
    assert await async_setup_component(hass, "http", {})
    from custom_components.slf_avalanche.view import async_register_view

    async_register_view(hass)
    async_register_view(hass)  # once only
    client = await hass_client()
    with patch("custom_components.slf_avalanche.view.async_get_bulletin", side_effect=TimeoutError):
        response = await client.get("/api/slf_avalanche/bulletin")
    assert response.status == 503
