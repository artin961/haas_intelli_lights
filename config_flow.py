"""Config flow for Intelli Lights integration."""

from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hello World."""

    def __init__(self):
        self.lights = []
        self.motion_sensors = []
        self.illuminance_sensors = []

    async def async_step_user(self, user_input=None):
        """Handle the initial step of the config flow."""
        # Fetch all light and motion sensor entities
        errors = {}

        if not self.lights or not self.motion_sensors or not self.illuminance_sensors:
            self.lights = [
                state.entity_id for state in self.hass.states.async_all("light")
            ]
            self.motion_sensors = [
                state.entity_id
                for state in self.hass.states.async_all("binary_sensor")
                if state.attributes.get("device_class") == "motion"
            ]
            self.illuminance_sensors = [
                state.entity_id
                for state in self.hass.states.async_all("sensor")
                if state.attributes.get("device_class") == "illuminance"
            ]

        if user_input is not None:
            # Handle saving the configuration
            try:
                if self.hass.data.get(DOMAIN) and user_input[
                    "light_entity"
                ] in self.hass.data[DOMAIN].get("instances", []):
                    _LOGGER.error(
                        "Light %s is already configured.", user_input["light_entity"]
                    )
                    raise ValueError(
                        f"Light {user_input['light_entity']} already configured"
                    )

                entity = self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
                return entity
            except ValueError as e:
                errors["base"] = f"Error: {e}"

            except Exception as e:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = f"Error: {e}"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required("light_entity"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=self.lights)
                    ),
                    vol.Optional("motion_sensor"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=self.motion_sensors)
                    ),
                    vol.Required("auto_off_delay", default=0): vol.All(
                        int, vol.Range(min=0, max=300)
                    ),
                    vol.Optional("illuminance_sensor"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=self.illuminance_sensors)
                    ),
                    vol.Required("illuminance_threshold", default=0): vol.All(
                        int, vol.Range(min=0, max=1000)
                    ),
                }
            ),
            errors=errors,
        )
