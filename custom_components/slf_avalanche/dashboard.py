"""Automatic dashboard and card-resource management.

Uses Home Assistant's internal Lovelace storage API (same verified pattern
as the author's other integrations). The dashboard is created once; each
location entry appends its own section exactly once (never touching user
edits). Removing the last config entry removes the dashboard and the card
resource again.
"""
from __future__ import annotations

import json
import logging

import voluptuous as vol

from homeassistant.components import frontend
from homeassistant.components.lovelace import dashboard as ll_dashboard
from homeassistant.components.lovelace.const import (
    CONF_ALLOW_SINGLE_WORD,
    CONF_ICON,
    CONF_REQUIRE_ADMIN,
    CONF_SHOW_IN_SIDEBAR,
    CONF_TITLE,
    CONF_URL_PATH,
    DOMAIN as LOVELACE_DOMAIN,
    LOVELACE_DATA,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_IMIS_STATIONS,
    CONF_MODE,
    CONF_NAME,
    DOMAIN,
    MODE_BULLETIN,
    STATIC_URL_BASE,
)
from .localization import t

_LOGGER = logging.getLogger(__name__)

DASHBOARD_URL_PATH = "slf-lawinen"
DASHBOARD_ICON = "mdi:snowflake-alert"

CARD_VERSION = "1.0.1"
CARD_RESOURCE_BASE = f"{STATIC_URL_BASE}/slf-imis-card.js"
CARD_RESOURCE_URL = f"{CARD_RESOURCE_BASE}?v={CARD_VERSION}"


async def async_ensure_dashboard(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register the card resource, create the dashboard, add this entry's section."""
    await _async_ensure_resource(hass)

    lovelace_data = hass.data.get(LOVELACE_DATA)
    if lovelace_data is None:
        _LOGGER.warning("Lovelace data not available — dashboard not set up")
        return

    if DASHBOARD_URL_PATH not in lovelace_data.dashboards:
        dashboards_collection = ll_dashboard.DashboardsCollection(hass)
        await dashboards_collection.async_load()
        try:
            item = await dashboards_collection.async_create_item(
                {
                    CONF_URL_PATH: DASHBOARD_URL_PATH,
                    CONF_TITLE: t("dashboard_title", hass),
                    CONF_ICON: DASHBOARD_ICON,
                    CONF_SHOW_IN_SIDEBAR: True,
                    CONF_REQUIRE_ADMIN: False,
                    CONF_ALLOW_SINGLE_WORD: True,
                }
            )
        except (HomeAssistantError, vol.Invalid) as err:
            _LOGGER.warning("Could not create the avalanche dashboard: %s", err)
            return
        storage = ll_dashboard.LovelaceStorage(hass, item)
        lovelace_data.dashboards[DASHBOARD_URL_PATH] = storage
        await storage.async_save(
            {
                "views": [
                    {
                        "title": t("dashboard_title", hass),
                        "path": "lawinen",
                        "type": "sections",
                        "icon": DASHBOARD_ICON,
                        "max_columns": 2,
                        "sections": [],
                    }
                ]
            }
        )
        frontend.async_register_built_in_panel(
            hass,
            LOVELACE_DOMAIN,
            frontend_url_path=DASHBOARD_URL_PATH,
            require_admin=False,
            show_in_sidebar=True,
            sidebar_title=t("dashboard_title", hass),
            sidebar_icon=DASHBOARD_ICON,
            config={"mode": "storage"},
            update=False,
        )
        _LOGGER.info("Avalanche dashboard set up at /%s", DASHBOARD_URL_PATH)

    await _async_append_entry_section(hass, entry, lovelace_data)


async def _async_append_entry_section(
    hass: HomeAssistant, entry: ConfigEntry, lovelace_data
) -> None:
    """Append this entry's section (bulletin location or IMIS stations) once."""
    mode = entry.data.get(CONF_MODE, MODE_BULLETIN)

    danger_entity = None
    region_entity = None
    if mode == MODE_BULLETIN:
        registry = er.async_get(hass)
        for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
            if reg_entry.unique_id == f"{entry.entry_id}_danger_level":
                danger_entity = reg_entry.entity_id
            elif reg_entry.unique_id == f"{entry.entry_id}_region":
                region_entity = reg_entry.entity_id
        if danger_entity is None:
            return
        marker = danger_entity
        stations = []
    else:
        stations = entry.options.get(
            CONF_IMIS_STATIONS, entry.data.get(CONF_IMIS_STATIONS) or []
        )
        if not stations:
            return
        marker = f'"station": "{str(stations[0]["code"]).lower()}"'

    storage = lovelace_data.dashboards.get(DASHBOARD_URL_PATH)
    if storage is None:
        return
    try:
        config = await storage.async_load(False)
    except HomeAssistantError as err:
        _LOGGER.debug("Could not load dashboard config: %s", err)
        return
    if not isinstance(config, dict) or not config.get("views"):
        return
    if marker in json.dumps(config):
        return  # section already present (added earlier or placed by the user)

    if mode == MODE_BULLETIN:
        cards = [
            {
                "type": "heading",
                "heading": entry.data.get(CONF_NAME) or entry.title,
                "icon": DASHBOARD_ICON,
                "badges": [
                    {"type": "entity", "entity": danger_entity, "show_state": True}
                ],
            },
            {"type": "tile", "entity": danger_entity, "color": "red", "grid_options": {"columns": 6}},
        ]
        if region_entity:
            cards.append(
                {"type": "tile", "entity": region_entity, "grid_options": {"columns": 6}}
            )
    else:
        cards = [
            {
                "type": "heading",
                "heading": t("imis_section_heading", hass),
                "icon": "mdi:ruler",
            }
        ]
        for station in stations:
            cards.append(
                {
                    "type": "custom:slf-imis-station-card",
                    "station": str(station["code"]).lower(),
                    "grid_options": {"columns": 6},
                }
            )

    config["views"][0].setdefault("sections", []).append(
        {"type": "grid", "column_span": 2, "cards": cards}
    )
    try:
        await storage.async_save(config)
    except HomeAssistantError as err:
        _LOGGER.warning("Could not add the location section to the dashboard: %s", err)
        return
    _LOGGER.info("Added section for %s to the avalanche dashboard", entry.title)


async def _async_ensure_resource(hass: HomeAssistant) -> None:
    """Register the bundled card as a Lovelace module resource."""
    lovelace_data = hass.data.get(LOVELACE_DATA)
    resources = getattr(lovelace_data, "resources", None)
    if resources is None:
        _LOGGER.warning(
            "Lovelace resources not available — add %s as a module resource manually",
            CARD_RESOURCE_URL,
        )
        return
    if not hasattr(resources, "async_create_item"):
        _LOGGER.info(
            "Lovelace runs in YAML mode — add %s as a module resource to use the card",
            CARD_RESOURCE_URL,
        )
        return

    if not resources.loaded:
        await resources.async_load()
        resources.loaded = True

    for item in resources.async_items():
        if CARD_RESOURCE_BASE in item.get("url", ""):
            if item.get("url") != CARD_RESOURCE_URL:
                await resources.async_update_item(item["id"], {"url": CARD_RESOURCE_URL})
                _LOGGER.info("Updated IMIS card resource to %s", CARD_RESOURCE_URL)
            return

    await resources.async_create_item({"res_type": "module", "url": CARD_RESOURCE_URL})
    _LOGGER.info("Registered IMIS card resource %s", CARD_RESOURCE_URL)


async def async_remove_dashboard(hass: HomeAssistant) -> None:
    """Remove the auto-created dashboard and the card resource (last entry gone)."""
    lovelace_data = hass.data.get(LOVELACE_DATA)
    if lovelace_data is None:
        return

    try:
        dashboards_collection = ll_dashboard.DashboardsCollection(hass)
        await dashboards_collection.async_load()
        for item in dashboards_collection.async_items():
            if item.get(CONF_URL_PATH) == DASHBOARD_URL_PATH:
                await dashboards_collection.async_delete_item(item["id"])
                lovelace_data.dashboards.pop(DASHBOARD_URL_PATH, None)
                frontend.async_remove_panel(hass, DASHBOARD_URL_PATH)
                _LOGGER.info("Removed dashboard /%s", DASHBOARD_URL_PATH)
                break
    except (HomeAssistantError, vol.Invalid) as err:
        _LOGGER.warning("Could not remove the avalanche dashboard: %s", err)

    try:
        resources = getattr(lovelace_data, "resources", None)
        if resources is not None and hasattr(resources, "async_delete_item"):
            if not resources.loaded:
                await resources.async_load()
                resources.loaded = True
            for item in list(resources.async_items()):
                if CARD_RESOURCE_BASE in item.get("url", ""):
                    await resources.async_delete_item(item["id"])
                    _LOGGER.info("Removed IMIS card resource")
                    break
    except HomeAssistantError as err:
        _LOGGER.warning("Could not remove the IMIS card resource: %s", err)
