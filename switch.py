import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN, CONF_GLOBAL_TOGGLE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the global toggle switch for Intelli Lights."""
    if CONF_GLOBAL_TOGGLE not in hass.data[DOMAIN]:
        switch = GlobalToggleSwitch()
        async_add_entities([switch], update_before_add=True)
        hass.data[DOMAIN][CONF_GLOBAL_TOGGLE] = switch


class GlobalToggleSwitch(SwitchEntity):
    """Global enable/disable switch for Intelli Lights."""

    def __init__(self):
        self._attr_name = "Intelli Lights Enabled"
        self._attr_unique_id = CONF_GLOBAL_TOGGLE
        self._is_on = True
        self._attr_entity_category = (
            EntityCategory.CONFIG
        )  # optional: shows in settings

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_turn_on(self, **kwargs):
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self._is_on = False
        self.async_write_ha_state()

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def name(self) -> str:
        return self._attr_name

    @property
    def unique_id(self) -> str:
        return self._attr_unique_id
