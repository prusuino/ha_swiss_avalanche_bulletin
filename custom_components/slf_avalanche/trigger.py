"""Triggers for the Swiss Avalanche Bulletin.

"Avalanche danger level reached" and "Avalanche danger level changed" for
the automation editor's trigger list. Both watch the danger-level sensor
of a bulletin entry; a target that expands to other entities (the entry's
device, an area) is narrowed to those sensors.

The trigger platform API arrived in Home Assistant 2026.10. On an older
version the module still imports, but offers no triggers.
"""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_FOR, CONF_OPTIONS, CONF_TARGET
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import DOMAIN

CONF_MINIMUM_LEVEL = "minimum_level"
DEFAULT_MINIMUM_LEVEL = 3

try:
    from homeassistant.helpers.automation import DomainSpec
    from homeassistant.helpers.trigger import (
        ATTR_BEHAVIOR,
        BEHAVIOR_ALL,
        BEHAVIOR_EACH,
        BEHAVIOR_FIRST,
        EntityTriggerBase,
        Trigger,
    )
except ImportError:  # Home Assistant before 2026.10: no trigger platform API
    TRIGGERS: dict = {}
else:
    DANGER_SPECS = {SENSOR_DOMAIN: DomainSpec()}

    # The core's entity-state schema (target + behavior + for) plus the
    # danger level option, spelled out because the nested options mapping
    # cannot be extended in place.
    LEVEL_SCHEMA = vol.Schema(
        {
            vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
            vol.Required(CONF_OPTIONS, default={}): {
                vol.Required(ATTR_BEHAVIOR, default=BEHAVIOR_EACH): vol.In(
                    [BEHAVIOR_FIRST, BEHAVIOR_ALL, BEHAVIOR_EACH]
                ),
                vol.Optional(CONF_FOR): cv.positive_time_period,
                vol.Optional(CONF_MINIMUM_LEVEL, default=DEFAULT_MINIMUM_LEVEL): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=5)
                ),
            },
        }
    )

    def _own_danger_entities(hass: HomeAssistant, entities: set[str]) -> set[str]:
        """Keep only the danger-level sensors of this integration."""
        registry = er.async_get(hass)
        return {
            entity_id
            for entity_id in entities
            if (entry := registry.async_get(entity_id)) is not None
            and entry.platform == DOMAIN
            and (entry.unique_id or "").endswith("_danger_level")
        }

    def _level(state: State) -> int | None:
        try:
            return int(float(state.state))
        except (TypeError, ValueError):
            return None

    class _LevelTrigger(EntityTriggerBase):
        """Base of the two triggers: remembers the last level of each sensor.

        The core skips every change out of "unknown" or "unavailable". For
        this sensor that is exactly when it matters: it has no value outside
        the season and while the SLF cannot be reached, so the first bulletin
        of the winter, or a level that rose during an outage, would never
        fire. Such a change is therefore let through and judged against the
        last level seen before the gap. The core asks is_valid_state for
        every reading with a value and only then is_valid_transition, so the
        levels are remembered there.
        """

        _domain_specs = DANGER_SPECS
        _excluded_from_states = frozenset()

        def __init__(self, hass: HomeAssistant, config) -> None:
            super().__init__(hass, config)
            self._last_level: dict[str, int] = {}
            self._previous_level: dict[str, int | None] = {}

        def entity_filter(self, entities: set[str]) -> set[str]:
            return _own_danger_entities(self._hass, super().entity_filter(entities))

        def _remember(self, state: State, level: int) -> None:
            self._previous_level[state.entity_id] = self._last_level.get(state.entity_id)
            self._last_level[state.entity_id] = level

        def _before(self, from_state: State, to_state: State) -> int | None:
            """The level before this change; across a gap the last one seen."""
            before = _level(from_state)
            return before if before is not None else self._previous_level.get(to_state.entity_id)

    class _DangerLevelChanged(_LevelTrigger):
        """The danger level of a bulletin entry changes to another level.

        Also fires for the first level after a time without one (the first
        bulletin of the season); a level that returns unchanged after a gap
        does not fire."""

        def is_valid_transition(self, from_state: State, to_state: State) -> bool:
            after = _level(to_state)
            return after is not None and self._before(from_state, to_state) != after

        def is_valid_state(self, state: State, report_not_triggered) -> bool:
            level = _level(state)
            if level is None:
                report_not_triggered("level_not_numeric", entity_id=state.entity_id)
                return False
            self._remember(state, level)
            return True

    class _DangerLevelReached(_LevelTrigger):
        """The danger level rises to the minimum level or above.

        Fires when the level goes from below the minimum, or from no level
        at all, to the minimum or higher; a change between two levels above
        the minimum does not fire again, and neither does a level that was
        already there before a gap."""

        _schema = LEVEL_SCHEMA

        def __init__(self, hass: HomeAssistant, config) -> None:
            super().__init__(hass, config)
            self._minimum = int(self._options.get(CONF_MINIMUM_LEVEL) or DEFAULT_MINIMUM_LEVEL)

        def is_valid_transition(self, from_state: State, to_state: State) -> bool:
            before = self._before(from_state, to_state)
            after = _level(to_state)
            return after is not None and after >= self._minimum and (before is None or before < self._minimum)

        def is_valid_state(self, state: State, report_not_triggered) -> bool:
            level = _level(state)
            if level is None:
                report_not_triggered("level_not_numeric", entity_id=state.entity_id)
                return False
            self._remember(state, level)
            return level >= self._minimum

    TRIGGERS: dict[str, type[Trigger]] = {
        "danger_level_reached": _DangerLevelReached,
        "danger_level_changed": _DangerLevelChanged,
    }


async def async_get_triggers(hass: HomeAssistant) -> dict:
    """Return the triggers of this integration."""
    return TRIGGERS
