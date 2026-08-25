"""Automation enable/disable switch — one per configured light."""

import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_AUTOMATION_ENABLED, LIGHT_ENTITY_INPUT_NAME

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one automation-enabled switch per light config entry."""
    light_entity = entry.data[LIGHT_ENTITY_INPUT_NAME]
    switch = AutomationEnabledSwitch(entry.entry_id, light_entity)
    async_add_entities([switch])

    hass.data.setdefault(DOMAIN, {}).setdefault(CONF_AUTOMATION_ENABLED, {})[
        light_entity
    ] = switch


def _slug(light_entity: str) -> str:
    """Return the object-id part of a light entity_id, e.g. 'bedroom' from 'light.bedroom'."""
    return light_entity.split(".", 1)[-1]


class AutomationEnabledSwitch(SwitchEntity):
    """Per-light switch to enable or pause the automation."""

    _attr_has_entity_name = False  # we set a fully-qualified name ourselves
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False

    def __init__(self, entry_id: str, light_entity: str) -> None:
        slug = _slug(light_entity)
        self._attr_unique_id = f"{entry_id}_automation_enabled"
        # e.g. "Bedroom Automation Enabled"
        self._attr_name = f"{slug.replace('_', ' ').title()} Automation Enabled"
        # explicit entity_id so the ID is predictable and includes the light name
        self.entity_id = f"switch.{slug}_automation_enabled"
        self._light_entity = light_entity
        self._attr_is_on = True

    async def async_turn_on(self, **kwargs) -> None:
        self._attr_is_on = True
        self.async_write_ha_state()
        _LOGGER.debug("Automation enabled for %s", self._light_entity)

    async def async_turn_off(self, **kwargs) -> None:
        self._attr_is_on = False
        self.async_write_ha_state()
        _LOGGER.debug("Automation paused for %s", self._light_entity)
