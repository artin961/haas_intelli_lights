import logging
from .light_control import LightControl
_LOGGER = logging.getLogger(__name__)

DOMAIN = "haas_intelli_lights"

async def async_setup(hass, config):
    """Set up the Intelligent Lighting component."""
    _LOGGER.debug("Setting up Intelligent Lighting component.")
    config = config.get(DOMAIN, {})
    light_control = LightControl(hass, config)
    await light_control.initialize()
    return True
