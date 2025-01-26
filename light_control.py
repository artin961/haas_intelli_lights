"""This class handles single light to track it motion sensor"""

import logging

# import asyncio
from datetime import datetime, timedelta
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType

# from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class LightControl:
    """Class for Intelligent lights control in HomeAssistant"""

    def __init__(self, hass: HomeAssistant, config: dict):
        self.hass = hass
        # Light to be controlled
        self.light_entity = config.get("light_entity")
        # Motion sensor to controll the light
        self.motion_sensor = config.get("motion_sensor")
        # Sensor to check before desiding if is dark enought
        self.illuminance_sensor = config.get("illuminance_sensor")
        # Threshold for darkness
        self.illuminance_threshold = config.get("illuminance_threshold", 0)
        # Auto turnoff delay if no motion
        self.auto_off_delay = config.get("auto_off_delay", 0)
        self.last_motion_time = None
        self.off_by_integration = False
        _LOGGER.warning("Loading %s", config)

    async def initialize(self):
        """Initialize motion tracking and start the scheduler."""

        if self.motion_sensor and self.auto_off_delay:
            _LOGGER.info(
                "Setting up motion sensor %s for %s",
                self.motion_sensor,
                self.light_entity,
            )
            # Track motion sensor state changes
            async_track_state_change_event(
                self.hass,
                self.motion_sensor,
                self._handle_motion_detected(self.light_entity),
            )

        if self.motion_sensor and self.auto_off_delay:
            _LOGGER.warning(
                "Setting up motion sensor %s for %s",
                self.motion_sensor,
                self.light_entity,
            )
            # Track motion sensor state changes
            async_track_state_change_event(
                self.hass,
                self.motion_sensor,
                self._handle_motion_detected(self.light_entity),
            )

        # Track light state changes (manual override detection)
        async_track_state_change_event(
            self.hass,
            self.light_entity,
            self._handle_light_state_change(self.light_entity),
        )

    async def check_timeout(self):
        """Check if the light should be turned off due to inactivity."""
        _LOGGER.debug("Checking timeouts for %s", self.light_entity)
        if not self.last_motion_time or self.auto_off_delay <= 0:
            return

        time_diff = datetime.now() - self.last_motion_time
        state = self.hass.states.get(self.light_entity)

        if (
            time_diff >= timedelta(minutes=self.auto_off_delay)
            and state
            and state.state == "on"
        ):
            _LOGGER.debug("Turning off %s due to timeout", self.light_entity)
            self.off_by_integration = True
            await self._light_turn_off()

    @callback
    def _handle_motion_detected(self, light_entity):
        """Handle motion detected events."""

        async def state_change(event):
            new_state = event.data.get("new_state")
            light_state = self.hass.states.get(light_entity)
            # Motion Detected
            if new_state and new_state.state == "on":
                _LOGGER.debug("Motion detected for %s.", light_entity)
                if light_state and light_state.state == "off":
                    await self._light_smart_turn_on()
                elif light_state and light_state.state == "on":
                    # Reset timer on motion while light is on
                    await self._light_reset_timer()

        return state_change

    @callback
    def _handle_light_state_change(self, light_entity):
        """Track manual light changes."""

        async def state_change(event):
            new_state = event.data.get("new_state")
            if new_state and new_state.state == "on":
                _LOGGER.debug("Turn on detected for %s.", light_entity)
                await self._light_reset_timer()

        return state_change

    async def _light_turn_on(self):
        """Turn on the light."""
        _LOGGER.debug("Turning on light %s.", self.light_entity)
        await self.hass.services.async_call(
            "light", "turn_on", {"entity_id": self.light_entity}
        )

    async def _light_turn_off(self):
        """Turn off the light."""
        _LOGGER.debug("Turning off light %s.", self.light_entity)
        await self.hass.services.async_call(
            "light", "turn_off", {"entity_id": self.light_entity}
        )

    async def _light_reset_timer(self):
        """Reset the motion timer for the given light."""
        _LOGGER.debug("Resetting timer for light %s.", self.light_entity)
        self.last_motion_time = datetime.now()

    async def _light_smart_turn_on(self):
        """Turn on the light if it was turned off by the integration."""
        state = self.hass.states.get(self.light_entity)
        if state and state.state == "off" and self.off_by_integration:
            # If there is light sensor defined and conditions are not met
            # return to prevent turning on
            if self.illuminance_sensor and self.illuminance_threshold:
                current_illuminance = self.hass.states.get(
                    self.illuminance_sensor
                ).state

                # Convert current illuminance to a number safely
                try:
                    current_illuminance = float(current_illuminance)
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Invalid illuminance value for %s: %s",
                        self.illuminance_sensor,
                        current_illuminance,
                    )
                    return

                if current_illuminance > self.illuminance_threshold:
                    _LOGGER.debug(
                        "Light check for %s, %s above %s",
                        self.light_entity,
                        current_illuminance,
                        self.illuminance_threshold,
                    )
                    return

            _LOGGER.debug("Reactivating light %s due to motion.", self.light_entity)
            await self._light_reset_timer()
            self.off_by_integration = False
            await self._light_turn_on()
