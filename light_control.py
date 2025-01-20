import logging
import asyncio
from datetime import datetime, timedelta
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

_LOGGER = logging.getLogger(__name__)

CHECK_INTERVAL = 30  # Seconds to run scheduler


class LightControl:
    """Class for Inteligrnt lights controll in HomeAssistant"""

    def __init__(self, hass: HomeAssistant, config: dict):
        self.hass = hass
        self.config = config
        self.lights = config.get("lights", {})
        self.motion_timestamps = {}  # Stores the last motion detection time
        self.off_by_integration = set()
        self._running = False

    async def initialize(self):
        """Initialize motion tracking and start the scheduler."""
        for light_entity, settings in self.lights.items():
            motion_sensor = settings.get("motion_sensor")

            if not motion_sensor:
                _LOGGER.warning("Skipping %s, no motion sensor defined.", light_entity)
                continue

            # Track motion sensor state changes
            async_track_state_change_event(
                self.hass, motion_sensor, self._handle_motion_detected(light_entity)
            )

            # Track light state changes (manual override detection)
            async_track_state_change_event(
                self.hass, light_entity, self._handle_light_state_change(light_entity)
            )

        self._running = True
        self.hass.loop.create_task(self._scheduler())

    @callback
    def _handle_light_state_change(self, light_entity):
        """Track manual light changes."""

        async def state_change(event):
            new_state = event.data.get("new_state")
            if new_state and new_state.state == "on":
                _LOGGER.debug("Turn on detected for %s.", light_entity)
                await self._light_reset_timer(light_entity)

        return state_change

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
                    await self._light_smart_turn_on(light_entity)
                elif light_state and light_state.state == "on":
                    # Reset timer on motion while light is on
                    await self._light_reset_timer(light_entity)

        return state_change

    async def _scheduler(self):
        """Background task to check motion timestamps and control lights."""

        while self._running:
            now = datetime.now()
            for light_entity, settings in self.lights.items():
                # Get auto off delay, 0 - Not configured
                auto_off_delay = settings.get("auto_off_delay", 0)
                if auto_off_delay:
                    last_motion_time = self.motion_timestamps.get(light_entity)

                    if last_motion_time:
                        # Calculate the time difference using timedelta
                        time_difference = now - last_motion_time
                        state = self.hass.states.get(light_entity)

                        # Check if the elapsed time is greater than or equal to the delay
                        if (
                            time_difference >= timedelta(minutes=auto_off_delay)
                            and state
                            and state.state == "on"
                        ):
                            _LOGGER.debug(
                                "Turning off %s due to timeout.", light_entity
                            )
                            await self._light_turn_off(light_entity)
                            self.off_by_integration.add(light_entity)

            await asyncio.sleep(CHECK_INTERVAL)

    async def _light_smart_turn_on(self, light_entity):
        """Turn on the light if it was turned off by the integration."""
        state = self.hass.states.get(light_entity)
        if state and state.state == "off" and light_entity in self.off_by_integration:
            _LOGGER.debug("Reactivating light %s due to motion.", light_entity)
            await self._light_reset_timer(light_entity)
            self.off_by_integration.remove(light_entity)
            await self._light_turn_on(light_entity)

    async def _light_reset_timer(self, light_entity):
        """Reset the motion timer for the given light."""
        _LOGGER.debug("Resetting timer for light %s.", light_entity)
        self.motion_timestamps[light_entity] = datetime.now()

    async def _light_turn_off(self, light_entity):
        """Turn off the light"""
        _LOGGER.debug("Turning off light %s.", light_entity)
        await self.hass.services.async_call(
            "light", "turn_off", {"entity_id": light_entity}
        )

    async def _light_turn_on(self, light_entity):
        """Turn on the light"""
        _LOGGER.debug("Turning on light %s.", light_entity)
        await self.hass.services.async_call(
            "light", "turn_on", {"entity_id": light_entity}
        )
