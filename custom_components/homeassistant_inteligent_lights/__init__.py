import logging
import sys
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.const import Platform

from .light_control import LightControl
from .const import (
    DOMAIN,
    CONF_AUTOMATION_ENABLED,
    LIGHT_ENTITY_INPUT_NAME,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SWITCH]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the domain-level reload service once at integration load time."""
    async def _handle_reload(call: ServiceCall) -> None:
        _LOGGER.debug("Reload service called — flushing module cache and reloading all entries")
        for mod in [k for k in sys.modules if k.startswith(f"custom_components.{DOMAIN}")]:
            del sys.modules[mod]
        for entry in hass.config_entries.async_entries(DOMAIN):
            await hass.config_entries.async_reload(entry.entry_id)

    hass.services.async_register(DOMAIN, "reload", _handle_reload)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a light automation instance from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {"instances": {}, CONF_AUTOMATION_ENABLED: {}})
    # Ensure both sub-dicts exist even if the domain was partially initialised
    domain_data.setdefault("instances", {})
    domain_data.setdefault(CONF_AUTOMATION_ENABLED, {})

    cfg = {**entry.data, **entry.options}
    light_entity = cfg[LIGHT_ENTITY_INPUT_NAME]

    if light_entity in domain_data["instances"]:
        _LOGGER.error("Light %s is already configured.", light_entity)
        return False

    light_control = LightControl(hass, cfg)
    await light_control.initialize()
    domain_data["instances"][light_entity] = light_control

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a light automation instance."""
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    light_entity = entry.data[LIGHT_ENTITY_INPUT_NAME]
    domain_data = hass.data.get(DOMAIN, {})

    instance: LightControl | None = domain_data.get("instances", {}).pop(
        light_entity, None
    )
    if instance is not None:
        instance.unload()
        _LOGGER.debug("Unloaded light control for %s", light_entity)

    domain_data.get(CONF_AUTOMATION_ENABLED, {}).pop(light_entity, None)

    return ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry (called automatically by OptionsFlowWithReload)."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
