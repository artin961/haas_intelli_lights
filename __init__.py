import logging
import asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .light_control import LightControl
from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)

PLATFORMS = []
CHECK_INTERVAL = 30


async def global_scheduler(hass: HomeAssistant):
    """Global scheduler to iterate over all light instances."""
    _LOGGER.info("Starting global light control scheduler")

    while True:
        if DOMAIN in hass.data and "instances" in hass.data[DOMAIN]:
            for light_control in hass.data[DOMAIN]["instances"].values():
                await light_control.check_timeout()

        await asyncio.sleep(CHECK_INTERVAL)  # Run every X seconds

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up individual light controls and start the scheduler."""

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {"instances": {}, "scheduler_task": None}

    light_config = entry.data

    # Avoid duplicate instances
    if light_config["light_entity"] in hass.data[DOMAIN]["instances"]:
        _LOGGER.error("Light %s is already configured.", light_config["light_entity"])
        return False
        #raise ValueError("Light entity already configured")

    # Create instance per light
    light_control = LightControl(hass, light_config)
    await light_control.initialize()

    hass.data[DOMAIN]["instances"][light_config["light_entity"]] = light_control

    # Start global scheduler if not already running
    if not hass.data[DOMAIN]["scheduler_task"]:
        hass.data[DOMAIN]["scheduler_task"] = hass.loop.create_task(global_scheduler(hass))

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an individual light instance."""
    light_config = entry.data
    light_entity = light_config["light_entity"]

    if light_entity in hass.data[DOMAIN]["instances"]:
        _LOGGER.info("Unloading light control for %s", light_entity)
        del hass.data[DOMAIN]["instances"][light_entity]

    # Stop scheduler if no more instances left
    if not hass.data[DOMAIN]["instances"]:
        if hass.data[DOMAIN]["scheduler_task"]:
            hass.data[DOMAIN]["scheduler_task"].cancel()
            hass.data[DOMAIN]["scheduler_task"] = None
            _LOGGER.info("Scheduler stopped as no lights are left.")

    return True

