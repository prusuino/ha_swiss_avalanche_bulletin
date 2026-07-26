"""Sensors for the SLF Swiss avalanche bulletin.

Data source: WSL Institute for Snow and Avalanche Research SLF (aws.slf.ch),
licensed under CC BY 4.0 — https://www.slf.ch/en/services-and-products/slf-data-service/
Attribution is required when using/displaying this data.
"""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UnitOfLength,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from . import RuntimeData
from .const import CONF_NAME, DOMAIN, MAX_PROBLEM_SENSORS
from .coordinator import ImisCoordinator, SlfAvalancheCoordinator
from .device import device_info
from .localization import danger_level_text, problem_type_text, t

ATTRIBUTION = "Data: WSL Institute for Snow and Avalanche Research SLF (CC BY 4.0)"

# Sensor key -> (unit, device_class, state_class, icon)
IMIS_SENSOR_TYPES: dict[str, tuple] = {
    "snow_height": (UnitOfLength.CENTIMETERS, None, SensorStateClass.MEASUREMENT, "mdi:snowflake"),
    "new_snow_1d": (UnitOfLength.CENTIMETERS, None, SensorStateClass.MEASUREMENT, "mdi:weather-snowy"),
    "air_temperature": (UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, None),
    "snow_surface_temperature": (UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, "mdi:thermometer-low"),
    "humidity": (PERCENTAGE, SensorDeviceClass.HUMIDITY, SensorStateClass.MEASUREMENT, None),
    "wind_speed": (UnitOfSpeed.METERS_PER_SECOND, SensorDeviceClass.WIND_SPEED, SensorStateClass.MEASUREMENT, None),
    "wind_gust": (UnitOfSpeed.METERS_PER_SECOND, SensorDeviceClass.WIND_SPEED, SensorStateClass.MEASUREMENT, "mdi:weather-windy"),
    "wind_direction": (DEGREE, None, SensorStateClass.MEASUREMENT, "mdi:compass-outline"),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data: RuntimeData = hass.data[DOMAIN][entry.entry_id]
    coordinator = data.bulletin

    entities: list[SensorEntity] = [
        SlfDangerLevelSensor(hass, coordinator, entry),
        SlfRegionSensor(hass, coordinator, entry),
    ]
    for i in range(MAX_PROBLEM_SENSORS):
        entities.append(SlfProblemSensor(hass, coordinator, entry, i))

    if data.imis is not None:
        for station in data.imis.stations:
            station_data = (data.imis.data or {}).get(station["code"]) or {}
            fields = set(station_data.get("fields") or [])
            if station_data.get("new_snow_1d") is not None or "snow_height" in fields:
                fields.add("new_snow_1d")
            for key in IMIS_SENSOR_TYPES:
                if key in fields:
                    entities.append(
                        ImisMeasurementSensor(hass, data.imis, entry, station, key)
                    )

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


class ImisMeasurementSensor(CoordinatorEntity[ImisCoordinator], SensorEntity):
    """One measured value of an IMIS station (official SLF measurement API)."""

    _attr_has_entity_name = False
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: ImisCoordinator,
        entry: ConfigEntry,
        station: dict,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._station = station
        self._key = key
        code = station["code"]
        unit, device_class, state_class, icon = IMIS_SENSOR_TYPES[key]
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        if icon:
            self._attr_icon = icon
        self._attr_name = t(f"imis_{key}", hass)
        self._attr_unique_id = f"{entry.entry_id}_imis_{code}_{key}"
        self.entity_id = f"sensor.slf_imis_{slugify(code)}_{key}"
        label = station.get("label") or code
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_imis_{code}")},
            name=t("imis_device_name", hass, name=f"{label} ({code})"),
            manufacturer=t("manufacturer", hass),
            model=t("imis_model", hass),
            entry_type="service",
        )

    def _station_data(self) -> dict:
        return (self.coordinator.data or {}).get(self._station["code"]) or {}

    @property
    def native_value(self):
        data = self._station_data()
        if self._key == "new_snow_1d":
            return data.get("new_snow_1d")
        return (data.get("values") or {}).get(self._key)

    @property
    def extra_state_attributes(self):
        attrs = {
            "station_code": self._station["code"],
            "station_name": self._station.get("label"),
            "elevation": self._station.get("elevation"),
            "distance_km": self._station.get("distance_km"),
            "measure_date": self._station_data().get("measure_date"),
        }
        if self._key == "snow_height":
            attrs["daily_snow_height"] = self._station_data().get("daily_snow_height")
        return attrs
