"""Config flow for Intelli Lights integration."""

from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    LIGHT_ENTYTY_INPUT_NAME,
    MOTION_SENSOR_INPUT_NAME,
    ILLUMMINANCE_SENSOR_INPUT_NAME,
    ILLUMINANCE_THRESHOLD_INPUT_NAME,
    AUTO_OFF_DELAY_INPUT_NAME,
)

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
                if state.attributes.get("device_class")
                in ("motion", "occupancy", "door", "window", "tamper")
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
                    LIGHT_ENTYTY_INPUT_NAME
                ] in self.hass.data[DOMAIN].get("instances", []):
                    _LOGGER.error(
                        "Light %s is already configured.",
                        user_input[LIGHT_ENTYTY_INPUT_NAME],
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
                    vol.Required(LIGHT_ENTYTY_INPUT_NAME): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=self.lights)
                    ),
                    vol.Optional(MOTION_SENSOR_INPUT_NAME): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=self.motion_sensors, multiple=True
                        )
                    ),
                    vol.Required(AUTO_OFF_DELAY_INPUT_NAME, default=0): vol.All(
                        vol.Coerce(float), vol.Range(min=0, max=300)
                    ),
                    vol.Optional(
                        ILLUMMINANCE_SENSOR_INPUT_NAME
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=self.illuminance_sensors, custom_value=True
                        )
                    ),
                    vol.Required(ILLUMINANCE_THRESHOLD_INPUT_NAME, default=0): vol.All(
                        int, vol.Range(min=0, max=1000)
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Method to register options flow"""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow to runtime changes of current entities."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.config_entry = config_entry
        self.hass: HomeAssistant = None  # still can use self.hass

    async def async_step_init(self, user_input=None):
        """Manage options for an existing light entry."""
        if user_input is not None:
            light_entity = self.config_entry.data[LIGHT_ENTYTY_INPUT_NAME]
            light_control = self.hass.data[DOMAIN]["instances"].get(light_entity)
            if light_control:
                # Update motion sensors
                new_motion_sensors = user_input.get(MOTION_SENSOR_INPUT_NAME, [])
                if isinstance(new_motion_sensors, str):
                    new_motion_sensors = [new_motion_sensors]  # normalize to list
                light_control.motion_sensors = new_motion_sensors

                # Update auto-off and threshold
                light_control.auto_off_delay = user_input.get(
                    AUTO_OFF_DELAY_INPUT_NAME, 0
                )
                light_control.illuminance_sensor = user_input.get(
                    ILLUMMINANCE_SENSOR_INPUT_NAME
                )
                light_control.illuminance_threshold = user_input.get(
                    ILLUMINANCE_THRESHOLD_INPUT_NAME, 0
                )

                # Re-initialize motion tracking if necessary
                await light_control.initialize()

            # Update the stored config entry
            return self.async_create_entry(title="", data=user_input)

        # Pre-fill current values
        options = self.config_entry.options
        data = self.config_entry.data

        motion_sensors = options.get(
            MOTION_SENSOR_INPUT_NAME, data.get(MOTION_SENSOR_INPUT_NAME, [])
        )
        if isinstance(motion_sensors, str):
            motion_sensors = [motion_sensors]

        illuminance_sensor = options.get(
            ILLUMMINANCE_SENSOR_INPUT_NAME, data.get(ILLUMMINANCE_SENSOR_INPUT_NAME)
        )
        auto_off_delay = options.get(
            AUTO_OFF_DELAY_INPUT_NAME, data.get(AUTO_OFF_DELAY_INPUT_NAME, 0)
        )
        illuminance_threshold = options.get(
            ILLUMINANCE_THRESHOLD_INPUT_NAME,
            data.get(ILLUMINANCE_THRESHOLD_INPUT_NAME, 0),
        )

        # Fetch current entities from HA for selectors
        motion_entities = [
            state.entity_id
            for state in self.hass.states.async_all("binary_sensor")
            if state.attributes.get("device_class")
            in ("motion", "occupancy", "door", "window", "tamper")
        ]
        illuminance_entities = [
            state.entity_id
            for state in self.hass.states.async_all("sensor")
            if state.attributes.get("device_class") == "illuminance"
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        AUTO_OFF_DELAY_INPUT_NAME, default=auto_off_delay
                    ): vol.All(vol.Coerce(float), vol.Range(min=0, max=300)),
                    vol.Optional(
                        MOTION_SENSOR_INPUT_NAME, default=motion_sensors
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=motion_entities, multiple=True
                        )
                    ),
                    vol.Optional(
                        ILLUMMINANCE_SENSOR_INPUT_NAME
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=illuminance_entities,
                            custom_value=True,
                        )
                    ),
                    vol.Required(
                        ILLUMINANCE_THRESHOLD_INPUT_NAME, default=illuminance_threshold
                    ): vol.All(int, vol.Range(min=0, max=1000)),
                }
            ),
        )
