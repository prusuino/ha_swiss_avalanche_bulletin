"""Sensors for the SLF Swiss avalanche bulletin.

Data source: WSL Institute for Snow and Avalanche Research SLF (aws.slf.ch),
licensed under CC BY 4.0 — https://www.slf.ch/en/services-and-products/slf-data-service/
Attribution is required when using/displaying this data.
"""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import CONF_NAME, DOMAIN, MAX_PROBLEM_SENSORS
from .coordinator import SlfAvalancheCoordinator
from .device import device_info
from .localization import danger_level_text, problem_type_text, t

ATTRIBUTION = "Data: WSL Institute for Snow and Avalanche Research SLF (CC BY 4.0)"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: SlfAvalancheCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = [
        SlfDangerLevelSensor(hass, coordinator, entry),
        SlfRegionSensor(hass, coordinator, entry),
    ]
    for i in range(MAX_PROBLEM_SENSORS):
        entities.append(SlfProblemSensor(hass, coordinator, entry, i))

    async_add_entities(entities)


def _slug(entry: ConfigEntry) -> str:
    name = entry.data.get(CONF_NAME) or entry.entry_id
    return slugify(name)


class SlfDangerLevelSensor(CoordinatorEntity[SlfAvalancheCoordinator], SensorEntity):
    """Current avalanche danger level (1-5) for the configured region."""

    _attr_has_entity_name = False
    _attr_attribution = ATTRIBUTION
    _attr_icon = "mdi:alert-octagon-outline"

    def __init__(
        self, hass: HomeAssistant, coordinator: SlfAvalancheCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = t("danger_level_sensor_name", hass)
        self._attr_unique_id = f"{entry.entry_id}_danger_level"
        self._attr_device_info = device_info(hass, entry)
        self.entity_id = f"sensor.slf_avalanche_danger_level_{_slug(entry)}"

    @property
    def native_value(self):
        return self.coordinator.data.get("danger_level")

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data
        return {
            "active": d.get("active"),
            "danger_text": danger_level_text(d.get("danger_main_value"), self.hass),
            "region": d.get("sector_name"),
            "valid_from": d.get("valid_from"),
            "valid_to": d.get("valid_to"),
            "next_update": d.get("next_update"),
            "publication_time": d.get("publication_time"),
            "unscheduled": d.get("unscheduled"),
            "danger_ratings_raw": d.get("danger_ratings_raw"),
        }


class SlfRegionSensor(CoordinatorEntity[SlfAvalancheCoordinator], SensorEntity):
    """Shows the SLF warning region determined for the configured coordinates."""

    _attr_has_entity_name = False
    _attr_attribution = ATTRIBUTION
    _attr_icon = "mdi:map-marker-radius-outline"

    def __init__(
        self, hass: HomeAssistant, coordinator: SlfAvalancheCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = t("region_sensor_name", hass)
        self._attr_unique_id = f"{entry.entry_id}_region"
        self._attr_device_info = device_info(hass, entry)
        self.entity_id = f"sensor.slf_avalanche_region_{_slug(entry)}"

    @property
    def native_value(self):
        return self.coordinator.data.get("sector_name")

    @property
    def extra_state_attributes(self):
        return {"sector_id": self.coordinator.data.get("sector_id")}


class SlfProblemSensor(CoordinatorEntity[SlfAvalancheCoordinator], SensorEntity):
    """One of up to 3 currently reported avalanche problems (empty if fewer are reported that day)."""

    _attr_has_entity_name = False
    _attr_attribution = ATTRIBUTION
    _attr_icon = "mdi:snowflake-alert"

    def __init__(
        self, hass: HomeAssistant, coordinator: SlfAvalancheCoordinator, entry: ConfigEntry, index: int
    ) -> None:
        super().__init__(coordinator)
        self._index = index
        self._attr_name = t("problem_sensor_name", hass, n=index + 1)
        self._attr_unique_id = f"{entry.entry_id}_problem_{index + 1}"
        self._attr_device_info = device_info(hass, entry)
        self.entity_id = f"sensor.slf_avalanche_problem_{index + 1}_{_slug(entry)}"

    def _problem(self) -> dict | None:
        problems = self.coordinator.data.get("avalanche_problems") or []
        if self._index < len(problems):
            return problems[self._index]
        return None

    @property
    def native_value(self):
        p = self._problem()
        if not p:
            return None
        return problem_type_text(p.get("problemType"), self.hass)

    @property
    def extra_state_attributes(self):
        p = self._problem()
        if not p:
            return {}
        elevation = p.get("elevation", {})
        return {
            "danger_level": p.get("dangerRatingValue"),
            "elevation_from": elevation.get("lowerBound"),
            "elevation_to": elevation.get("upperBound"),
            "aspects": p.get("aspects"),
            "comment": p.get("comment"),
        }
