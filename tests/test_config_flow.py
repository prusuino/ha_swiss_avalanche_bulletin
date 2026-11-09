"""Config flow tests: bulletin per location (sector lookup, duplicate,
unreachable service, reconfigure) and IMIS favourites (selection, station
taken by another entry, unavailable list, reconfigure)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.slf_avalanche.const import (
    CONF_IMIS_STATIONS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
    DOMAIN,
    MODE_BULLETIN,
    MODE_IMIS,
)

FLOW = "custom_components.slf_avalanche.config_flow."
STATIONS = [
    {"code": "WFJ2", "label": "Weissfluhjoch", "lat": 46.83, "lon": 9.81, "elevation": 2536, "type": "SNOW_FLAT"},
    {"code": "KLO2", "label": "Klosters", "lat": 46.87, "lon": 9.88, "elevation": 2147, "type": "SNOW_SLOPE"},
]


@pytest.fixture
def fake_slf():
    with (
        patch(FLOW + "async_resolve_sector", return_value={"sector_id": "1111", "sector_name": "Davos"}),
        patch(FLOW + "async_fetch_stations", return_value=STATIONS),
    ):
        yield


async def _menu(hass, step):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": step})
    assert result["step_id"] == step
    return result


async def test_bulletin_setup_names_the_entry_after_the_sector(hass: HomeAssistant, enable_custom_integrations, fake_slf) -> None:
    result = await _menu(hass, "bulletin")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_LATITUDE: 46.8, CONF_LONGITUDE: 9.83})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_MODE: MODE_BULLETIN, CONF_NAME: "Davos", CONF_LATITUDE: 46.8, CONF_LONGITUDE: 9.83}
    assert "Davos" in result["title"]
    assert result["result"].unique_id == "46.8_9.83"


async def test_bulletin_own_name_wins(hass: HomeAssistant, enable_custom_integrations, fake_slf) -> None:
    result = await _menu(hass, "bulletin")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_NAME: "Skihütte", CONF_LATITUDE: 46.8, CONF_LONGITUDE: 9.83})
    assert result["data"][CONF_NAME] == "Skihütte"


async def test_bulletin_without_region_is_cannot_connect(hass: HomeAssistant, enable_custom_integrations) -> None:
    with patch(FLOW + "async_resolve_sector", side_effect=UpdateFailed("no region")):
        result = await _menu(hass, "bulletin")
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_LATITUDE: 52.5, CONF_LONGITUDE: 13.4})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_bulletin_same_location_twice_is_refused(hass: HomeAssistant, enable_custom_integrations, fake_slf) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id="46.8_9.83", title="SLF", data={CONF_MODE: MODE_BULLETIN, CONF_LATITUDE: 46.8, CONF_LONGITUDE: 9.83}).add_to_hass(hass)
    result = await _menu(hass, "bulletin")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_LATITUDE: 46.8, CONF_LONGITUDE: 9.83})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bulletin_reconfigure_moves_the_location(hass: HomeAssistant, enable_custom_integrations, fake_slf) -> None:
    entry = MockConfigEntry(domain=DOMAIN, unique_id="46.8_9.83", title="SLF Davos", data={CONF_MODE: MODE_BULLETIN, CONF_NAME: "Davos", CONF_LATITUDE: 46.8, CONF_LONGITUDE: 9.83})
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id})
    assert result["step_id"] == "reconfigure_bulletin"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_LATITUDE: 46.5, CONF_LONGITUDE: 8.0})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == "46.5_8.0"
    assert entry.data[CONF_LATITUDE] == 46.5


async def test_imis_setup_stores_compact_station_records(hass: HomeAssistant, enable_custom_integrations, fake_slf) -> None:
    result = await _menu(hass, "imis")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_IMIS_STATIONS: ["WFJ2", "KLO2"]})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "IMIS Weissfluhjoch, Klosters"
    stations = result["data"][CONF_IMIS_STATIONS]
    assert [s["code"] for s in stations] == ["WFJ2", "KLO2"]
    assert stations[0]["elevation"] == 2536 and "distance_km" in stations[0]
    assert result["data"][CONF_MODE] == MODE_IMIS


async def test_imis_station_of_another_entry_is_refused(hass: HomeAssistant, enable_custom_integrations, fake_slf) -> None:
    MockConfigEntry(domain=DOMAIN, title="IMIS", data={CONF_MODE: MODE_IMIS, CONF_IMIS_STATIONS: [{"code": "WFJ2", "label": "Weissfluhjoch"}]}).add_to_hass(hass)
    result = await _menu(hass, "imis")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_IMIS_STATIONS: ["WFJ2"]})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_IMIS_STATIONS: "station_already_configured"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_IMIS_STATIONS: []})
    assert result["errors"] == {CONF_IMIS_STATIONS: "no_station"}


async def test_imis_list_unavailable_aborts(hass: HomeAssistant, enable_custom_integrations) -> None:
    with patch(FLOW + "async_fetch_stations", side_effect=TimeoutError()):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "imis"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "imis_unavailable"


async def test_imis_reconfigure_replaces_the_selection(hass: HomeAssistant, enable_custom_integrations, fake_slf) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, title="IMIS Weissfluhjoch",
        data={CONF_MODE: MODE_IMIS, CONF_IMIS_STATIONS: [{"code": "WFJ2", "label": "Weissfluhjoch"}]},
        options={CONF_IMIS_STATIONS: [{"code": "WFJ2", "label": "Weissfluhjoch"}], "other": 1},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id})
    assert result["step_id"] == "reconfigure_imis"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_IMIS_STATIONS: ["KLO2"]})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert [s["code"] for s in entry.data[CONF_IMIS_STATIONS]] == ["KLO2"]
    assert CONF_IMIS_STATIONS not in entry.options  # an older selection in the options would win
    assert entry.options == {"other": 1}
    assert entry.title == "IMIS Klosters"
