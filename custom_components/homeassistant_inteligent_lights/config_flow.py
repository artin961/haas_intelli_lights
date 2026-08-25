"""Config flow for Intelli Lights integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    LIGHT_ENTITY_INPUT_NAME,
    MOTION_SENSOR_INPUT_NAME,
    ILLUMINANCE_SENSOR_INPUT_NAME,
    ILLUMINANCE_THRESHOLD_INPUT_NAME,
    AUTO_OFF_DELAY_INPUT_NAME,
    EXIT_SENSOR_INPUT_NAME,
    EXIT_DELAY_INPUT_NAME,
)

_LOGGER = logging.getLogger(__name__)


def _light_entities(hass: HomeAssistant) -> list[str]:
    return [s.entity_id for s in hass.states.async_all("light")]


def _motion_entities(hass: HomeAssistant) -> list[str]:
    return [
        s.entity_id
        for s in hass.states.async_all("binary_sensor")
        if s.attributes.get("device_class")
        in ("motion", "occupancy", "door", "window", "tamper")
    ]


def _illuminance_entities(hass: HomeAssistant) -> list[str]:
    return [
        s.entity_id
        for s in hass.states.async_all("sensor")
        if s.attributes.get("device_class") == "illuminance"
    ]


def _illuminance_selector(hass: HomeAssistant) -> selector.SelectSelector:
    """Selector for illuminance sensor. No custom_value — user must pick from list or clear."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=_illuminance_entities(hass),
            multiple=False,
            custom_value=False,
        )
    )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for a single light automation."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            light = user_input[LIGHT_ENTITY_INPUT_NAME]

            # Prevent duplicates
            existing = {
                e.data[LIGHT_ENTITY_INPUT_NAME]
                for e in self._async_current_entries()
            }
            if light in existing:
                errors["base"] = "already_configured"
            else:
                await self.async_set_unique_id(light)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_NAME: user_input[CONF_NAME],
                        LIGHT_ENTITY_INPUT_NAME: light,
                    },
                    options={
                        MOTION_SENSOR_INPUT_NAME: user_input.get(
                            MOTION_SENSOR_INPUT_NAME, []
                        ),
                        AUTO_OFF_DELAY_INPUT_NAME: user_input.get(
                            AUTO_OFF_DELAY_INPUT_NAME, 5
                        ),
                        ILLUMINANCE_SENSOR_INPUT_NAME: user_input.get(
                            ILLUMINANCE_SENSOR_INPUT_NAME
                        ) or None,
                        ILLUMINANCE_THRESHOLD_INPUT_NAME: user_input.get(
                            ILLUMINANCE_THRESHOLD_INPUT_NAME, 0
                        ),
                        EXIT_SENSOR_INPUT_NAME: user_input.get(
                            EXIT_SENSOR_INPUT_NAME, []
                        ),
                        EXIT_DELAY_INPUT_NAME: user_input.get(
                            EXIT_DELAY_INPUT_NAME, 1
                        ),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): str,
                    vol.Required(LIGHT_ENTITY_INPUT_NAME): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=_light_entities(self.hass)
                        )
                    ),
                    vol.Optional(MOTION_SENSOR_INPUT_NAME): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=_motion_entities(self.hass), multiple=True
                        )
                    ),
                    vol.Required(AUTO_OFF_DELAY_INPUT_NAME, default=5): vol.All(
                        vol.Coerce(float), vol.Range(min=0, max=300)
                    ),
                    vol.Optional(ILLUMINANCE_SENSOR_INPUT_NAME): _illuminance_selector(
                        self.hass
                    ),
                    vol.Required(ILLUMINANCE_THRESHOLD_INPUT_NAME, default=0): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=100000)
                    ),
                    vol.Optional(EXIT_SENSOR_INPUT_NAME): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=_motion_entities(self.hass), multiple=True
                        )
                    ),
                    vol.Optional(EXIT_DELAY_INPUT_NAME, default=1): vol.All(
                        vol.Coerce(float), vol.Range(min=0, max=60)
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlowWithReload):
    """Options flow — automatically reloads the entry on save."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            ill = user_input.get(ILLUMINANCE_SENSOR_INPUT_NAME) or None
            exit_s = user_input.get(EXIT_SENSOR_INPUT_NAME, [])
            if isinstance(exit_s, str):
                exit_s = [exit_s]
            motion = user_input.get(MOTION_SENSOR_INPUT_NAME, [])
            if isinstance(motion, str):
                motion = [motion]

            _LOGGER.debug(
                "OptionsFlow saving: ill=%r motion=%r exit_sensors=%r "
                "auto_off_delay=%r exit_delay=%r threshold=%r",
                ill,
                motion,
                exit_s,
                user_input.get(AUTO_OFF_DELAY_INPUT_NAME),
                user_input.get(EXIT_DELAY_INPUT_NAME),
                user_input.get(ILLUMINANCE_THRESHOLD_INPUT_NAME),
            )

            return self.async_create_entry(data={
                AUTO_OFF_DELAY_INPUT_NAME: user_input[AUTO_OFF_DELAY_INPUT_NAME],
                MOTION_SENSOR_INPUT_NAME: motion,
                ILLUMINANCE_SENSOR_INPUT_NAME: ill,
                ILLUMINANCE_THRESHOLD_INPUT_NAME: user_input[ILLUMINANCE_THRESHOLD_INPUT_NAME],
                EXIT_SENSOR_INPUT_NAME: exit_s,
                EXIT_DELAY_INPUT_NAME: user_input.get(EXIT_DELAY_INPUT_NAME, 1),
            })

        opts = self.config_entry.options
        _LOGGER.debug("OptionsFlow opened, current options: %s", dict(opts))

        current_motion: list[str] = opts.get(MOTION_SENSOR_INPUT_NAME, [])
        if isinstance(current_motion, str):
            current_motion = [current_motion]

        current_ill: str | None = opts.get(ILLUMINANCE_SENSOR_INPUT_NAME)
        current_delay: float = opts.get(AUTO_OFF_DELAY_INPUT_NAME, 5)
        current_threshold: int = opts.get(ILLUMINANCE_THRESHOLD_INPUT_NAME, 0)

        current_exit_sensors: list[str] = opts.get(EXIT_SENSOR_INPUT_NAME, [])
        if isinstance(current_exit_sensors, str):
            current_exit_sensors = [current_exit_sensors]
        current_exit_delay: float = opts.get(EXIT_DELAY_INPUT_NAME, 1)

        motion_entities = _motion_entities(self.hass)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(AUTO_OFF_DELAY_INPUT_NAME): vol.All(
                            vol.Coerce(float), vol.Range(min=0, max=300)
                        ),
                        vol.Optional(
                            MOTION_SENSOR_INPUT_NAME
                        ): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=motion_entities, multiple=True
                            )
                        ),
                        # No default= — suggested_values pre-fills UI without
                        # voluptuous injecting the old value when field is cleared
                        vol.Optional(ILLUMINANCE_SENSOR_INPUT_NAME): _illuminance_selector(
                            self.hass
                        ),
                        vol.Required(ILLUMINANCE_THRESHOLD_INPUT_NAME): vol.All(
                            vol.Coerce(int), vol.Range(min=0, max=100000)
                        ),
                        vol.Optional(EXIT_SENSOR_INPUT_NAME): selector.SelectSelector(
                            selector.SelectSelectorConfig(
                                options=motion_entities, multiple=True
                            )
                        ),
                        vol.Optional(EXIT_DELAY_INPUT_NAME): vol.All(
                            vol.Coerce(float), vol.Range(min=0, max=60)
                        ),
                    }
                ),
                {
                    AUTO_OFF_DELAY_INPUT_NAME: current_delay,
                    MOTION_SENSOR_INPUT_NAME: current_motion,
                    ILLUMINANCE_SENSOR_INPUT_NAME: current_ill,
                    ILLUMINANCE_THRESHOLD_INPUT_NAME: current_threshold,
                    EXIT_SENSOR_INPUT_NAME: current_exit_sensors,
                    EXIT_DELAY_INPUT_NAME: current_exit_delay,
                },
            ),
        )
