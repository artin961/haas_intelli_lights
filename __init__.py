import logging

_LOGGER = logging.getLogger(__name__)

DOMAIN = "intelligent_lighting"

async def async_setup(hass, config):
    """Set up the Intelligent Lighting component."""
    _LOGGER.debug("Setting up Intelligent Lighting component.")
    from .light_control import LightControl
    config = config.get(DOMAIN, {})
    light_control = LightControl(hass, config)
    await light_control.initialize()
    return True
