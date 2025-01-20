import logging
import asyncio
from datetime import datetime, timedelta
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

_LOGGER = logging.getLogger(__name__)

CHECK_INTERVAL = 1  # Check lights every second

class LightControl:
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
                _LOGGER.warning(f"Skipping {light_entity}, no motion sensor defined.")
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
        def state_change(event):
            new_state = event.data.get("new_state")
            if new_state and new_state.state == "on":
                self.motion_timestamps[light_entity] = datetime.now()
                _LOGGER.debug(f"Turn on detected for {light_entity}, timer reset.")
        return state_change

    @callback
    def _handle_motion_detected(self, light_entity):
        """Handle motion detected events."""
        def state_change(event):
            new_state = event.data.get("new_state")
            light_state = self.hass.states.get(light_entity)
            # Motion Detected
            if new_state and new_state.state == "on":
                # Off turn it on if off by automation
                if light_state and light_state.state == "off":
                    _LOGGER.debug(f"Motion detected for {light_entity} while being off.")
                    self.hass.loop.create_task(self._turn_on_light(light_entity))
                # On reset timer
                elif light_state and light_state.state == "on":
                    _LOGGER.debug(f"Motion detected for {light_entity}, resetting timer.")
                    self.motion_timestamps[light_entity] = datetime.now()
        return state_change

    async def _scheduler(self):
        """Background task to check motion timestamps and control lights."""
        while self._running:
            now = datetime.now()
            for light_entity, settings in self.lights.items():
                delay = settings.get("delay", 60)
                last_motion_time = self.motion_timestamps.get(light_entity)

                if last_motion_time:
                    elapsed_time = (now - last_motion_time).total_seconds()
                    state = self.hass.states.get(light_entity)

                    if elapsed_time >= delay and state and state.state == "on":
                        _LOGGER.debug(f"Turning off {light_entity} due to timeout.")
                        await self.hass.services.async_call(
                            "light", "turn_off", {"entity_id": light_entity}
                        )
                        self.off_by_integration.add(light_entity)

            await asyncio.sleep(CHECK_INTERVAL)

    async def _turn_on_light(self, light_entity):
        """Turn on the light if it was turned off by the integration."""
        state = self.hass.states.get(light_entity)
        if state and state.state == "off":
            _LOGGER.debug(f"Light {light_entity} is currently off.")
            if light_entity in self.off_by_integration:
                _LOGGER.debug(f"Reactivating light {light_entity} due to motion and resetting the timer.")
                #self.motion_timestamps[light_entity] = datetime.now() #it will be detecteds
                await self.hass.services.async_call(
                    "light", "turn_on", {"entity_id": light_entity}
                )
                self.off_by_integration.remove(light_entity)
            else:
                _LOGGER.debug(f"Wont turn on light {light_entity} as not turned off by aotomation.")

