"""Single-light intelligent control: motion tracking, timeouts, illuminance gating."""

import logging
import time
from typing import Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_call_later

from .const import (
    DOMAIN,
    CONF_AUTOMATION_ENABLED,
    LIGHT_ENTITY_INPUT_NAME,
    MOTION_SENSOR_INPUT_NAME,
    ILLUMINANCE_SENSOR_INPUT_NAME,
    ILLUMINANCE_THRESHOLD_INPUT_NAME,
    AUTO_OFF_DELAY_INPUT_NAME,
    EXIT_SENSOR_INPUT_NAME,
    EXIT_DELAY_INPUT_NAME,
)

_LOGGER = logging.getLogger(__name__)

_ACTIVE_STATES = frozenset({"on", "open", "detected", "occupied"})
_INACTIVE_STATES = frozenset({"off", "clear", "closed"})


class LightControl:
    """Manages automation for a single light entity."""

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        self.hass = hass
        self.light_entity: str = config[LIGHT_ENTITY_INPUT_NAME]

        motion = config.get(MOTION_SENSOR_INPUT_NAME, [])
        self.motion_sensors: list[str] = (
            [motion] if isinstance(motion, str) else list(motion)
        )

        exit_sensors = config.get(EXIT_SENSOR_INPUT_NAME, [])
        self.exit_sensors: list[str] = (
            [exit_sensors] if isinstance(exit_sensors, str) else list(exit_sensors)
        )

        self.illuminance_sensor: str | None = config.get(ILLUMINANCE_SENSOR_INPUT_NAME)
        self.illuminance_threshold: float = float(
            config.get(ILLUMINANCE_THRESHOLD_INPUT_NAME, 0)
        )
        self.auto_off_delay: float = float(config.get(AUTO_OFF_DELAY_INPUT_NAME, 0))
        self.exit_delay: float = float(config.get(EXIT_DELAY_INPUT_NAME, 1))

        self._off_by_integration: bool = False

        # Timestamp of the last room-sensor active transition (monotonic seconds).
        # Used to suppress exit-sensor triggers that race with room motion.
        self._last_room_motion: float = 0.0

        self._motion_unsubs: list[Callable] = []
        self._exit_unsubs: list[Callable] = []
        self._light_unsub: Callable | None = None
        self._timeout_cancel: Callable | None = None

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """(Re-)subscribe to state changes. Safe to call multiple times."""
        self._unsubscribe_motion()
        self._unsubscribe_exit()

        if self._light_unsub is not None:
            self._light_unsub()
            self._light_unsub = None

        self._cancel_timeout()

        if self.motion_sensors and self.auto_off_delay > 0:
            for sensor in self.motion_sensors:
                unsub = async_track_state_change_event(
                    self.hass, sensor, self._on_motion_state_change
                )
                self._motion_unsubs.append(unsub)
            _LOGGER.debug(
                "Tracking %d motion sensors for %s",
                len(self.motion_sensors),
                self.light_entity,
            )

        if self.exit_sensors:
            for sensor in self.exit_sensors:
                unsub = async_track_state_change_event(
                    self.hass, sensor, self._on_exit_sensor_change
                )
                self._exit_unsubs.append(unsub)
            _LOGGER.debug(
                "Tracking %d exit sensors for %s",
                len(self.exit_sensors),
                self.light_entity,
            )

        self._light_unsub = async_track_state_change_event(
            self.hass, self.light_entity, self._on_light_state_change
        )

    def unload(self) -> None:
        """Remove all subscriptions and cancel pending timeouts."""
        self._unsubscribe_motion()
        self._unsubscribe_exit()
        if self._light_unsub is not None:
            self._light_unsub()
            self._light_unsub = None
        self._cancel_timeout()

    def _unsubscribe_motion(self) -> None:
        for unsub in self._motion_unsubs:
            unsub()
        self._motion_unsubs = []

    def _unsubscribe_exit(self) -> None:
        for unsub in self._exit_unsubs:
            unsub()
        self._exit_unsubs = []

    # ------------------------------------------------------------------
    # Automation-enabled gate
    # ------------------------------------------------------------------

    def _automation_enabled(self) -> bool:
        switch = self.hass.data.get(DOMAIN, {}).get(CONF_AUTOMATION_ENABLED, {}).get(
            self.light_entity
        )
        return switch is None or switch.is_on

    # ------------------------------------------------------------------
    # Timeout management
    # ------------------------------------------------------------------

    def _schedule_timeout(self, delay_minutes: float | None = None) -> None:
        """Schedule auto-off. Uses auto_off_delay unless delay_minutes is given."""
        self._cancel_timeout()
        delay = delay_minutes if delay_minutes is not None else self.auto_off_delay
        if delay <= 0:
            return

        mode = "exit" if delay_minutes is not None else "normal"
        _LOGGER.debug(
            "Timer set for %s: %.1f min (%s)",
            self.light_entity,
            delay,
            mode,
        )

        @callback
        def _timeout_fired(_now):
            self._timeout_cancel = None
            self.hass.async_create_task(self._check_timeout())

        self._timeout_cancel = async_call_later(self.hass, delay * 60, _timeout_fired)

    def _cancel_timeout(self) -> None:
        if self._timeout_cancel is not None:
            self._timeout_cancel()
            self._timeout_cancel = None

    # ------------------------------------------------------------------
    # Timeout check
    # ------------------------------------------------------------------

    async def _check_timeout(self) -> None:
        """Turn off the light if no room sensor is still active."""
        if not self._automation_enabled():
            return

        light_state = self.hass.states.get(self.light_entity)
        if not light_state or light_state.state != "on":
            return

        for sensor in self.motion_sensors:
            sensor_state = self.hass.states.get(sensor)
            if sensor_state is None:
                _LOGGER.warning(
                    "Motion sensor %s not found (skipping for %s)",
                    sensor,
                    self.light_entity,
                )
                continue
            if sensor_state.state.lower() in _ACTIVE_STATES:
                _LOGGER.debug(
                    "Motion still active on %s for %s, resetting timer",
                    sensor,
                    self.light_entity,
                )
                self._schedule_timeout()
                return

        _LOGGER.debug("Timeout expired for %s — turning off", self.light_entity)
        self._off_by_integration = True
        await self.hass.services.async_call(
            "light", "turn_off", {"entity_id": self.light_entity}
        )

    # ------------------------------------------------------------------
    # Room motion callback
    # ------------------------------------------------------------------

    @callback
    def _on_motion_state_change(self, event) -> None:
        if not self._automation_enabled():
            return

        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if new_state is None:
            return

        new = new_state.state.lower()
        old = old_state.state.lower() if old_state else None

        if new not in _ACTIVE_STATES:
            return

        # Record timestamp whenever room motion becomes active
        self._last_room_motion = time.monotonic()

        if old in _ACTIVE_STATES:
            light_state = self.hass.states.get(self.light_entity)
            if light_state and light_state.state == "on":
                self._schedule_timeout()
            return

        light_state = self.hass.states.get(self.light_entity)
        _LOGGER.debug(
            "Motion -> active on %s for %s (light=%s, off_by_integration=%s)",
            event.data.get("entity_id"),
            self.light_entity,
            light_state.state if light_state else "unknown",
            self._off_by_integration,
        )

        if light_state and light_state.state == "on":
            # Room motion while exit timer may be running — cancel it, go back to normal
            self._schedule_timeout()
        elif light_state and light_state.state == "off":
            if self._off_by_integration:
                self.hass.async_create_task(self._smart_turn_on())
            else:
                _LOGGER.debug(
                    "Skipping turn-on for %s — was turned off manually",
                    self.light_entity,
                )

    # ------------------------------------------------------------------
    # Exit sensor callback
    # ------------------------------------------------------------------

    @callback
    def _on_exit_sensor_change(self, event) -> None:
        """Shorten the timeout when someone leaves through an adjacent area."""
        if not self._automation_enabled():
            return

        new_state = event.data.get("new_state")
        if new_state is None:
            return

        if new_state.state.lower() not in _ACTIVE_STATES:
            return

        light_state = self.hass.states.get(self.light_entity)
        if not light_state or light_state.state != "on":
            return

        # Ignore if room motion fired recently — person is still in the room
        # (handles simultaneous room+exit firing and the girlfriend-hallway case)
        elapsed = time.monotonic() - self._last_room_motion
        # exit_window = self.exit_delay * 60
        # if elapsed < exit_window:
        #     _LOGGER.debug(
        #         "Exit sensor %s fired for %s but room motion was %0.1fs ago — ignoring",
        #         event.data.get("entity_id"),
        #         self.light_entity,
        #         elapsed,
        #     )
        #     return

        _LOGGER.debug(
            "Exit sensor %s fired for %s — switching to short timer (%.1f min)",
            event.data.get("entity_id"),
            self.light_entity,
            self.exit_delay,
        )
        # Reset to the short exit timer (cancels whatever was running)
        self._schedule_timeout(delay_minutes=self.exit_delay)

    # ------------------------------------------------------------------
    # Light state callback
    # ------------------------------------------------------------------

    @callback
    def _on_light_state_change(self, event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        if new_state.state == "on":
            _LOGGER.debug("Light %s turned on — starting timer", self.light_entity)
            self._schedule_timeout()

        elif new_state.state == "off":
            self._cancel_timeout()
            if not self._off_by_integration:
                _LOGGER.debug(
                    "Light %s turned off by user — blocking motion re-trigger",
                    self.light_entity,
                )
            else:
                _LOGGER.debug(
                    "Light %s turned off by integration", self.light_entity
                )

    # ------------------------------------------------------------------
    # Smart turn-on (respects illuminance)
    # ------------------------------------------------------------------

    async def _smart_turn_on(self) -> None:
        if self.illuminance_sensor and self.illuminance_threshold > 0:
            ill_state = self.hass.states.get(self.illuminance_sensor)
            if ill_state is None:
                _LOGGER.warning(
                    "Illuminance sensor %s missing for %s — failing open, turning on",
                    self.illuminance_sensor,
                    self.light_entity,
                )
            elif ill_state.state in ("unavailable", "unknown"):
                _LOGGER.warning(
                    "Illuminance sensor %s is %s for %s — failing open, turning on",
                    self.illuminance_sensor,
                    ill_state.state,
                    self.light_entity,
                )
            else:
                try:
                    lux = float(ill_state.state)
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Invalid illuminance value '%s' from %s for %s — failing open, turning on",
                        ill_state.state,
                        self.illuminance_sensor,
                        self.light_entity,
                    )
                else:
                    if lux > self.illuminance_threshold:
                        _LOGGER.debug(
                            "Illuminance %.1f lx > threshold %.1f lx for %s — not turning on",
                            lux,
                            self.illuminance_threshold,
                            self.light_entity,
                        )
                        return

        _LOGGER.debug("Turning on %s via automation", self.light_entity)
        self._off_by_integration = False
        self._schedule_timeout()
        await self.hass.services.async_call(
            "light", "turn_on", {"entity_id": self.light_entity}
        )
