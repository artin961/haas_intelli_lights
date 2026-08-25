# haas_intelli_lights — Claude Code context

## Project overview

Home Assistant custom integration for event-driven intelligent light automation. One config entry per light. Lives in `custom_components/homeassistant_inteligent_ights/` (the directory name has a typo — do not rename it, HACS users have it installed under that path).

## File map

| File | Purpose |
|------|---------|
| `const.py` | All constant/key names. Single source of truth — change a key here only. |
| `light_control.py` | `LightControl` class — all automation logic for one light |
| `switch.py` | `AutomationEnabledSwitch` — one HA switch entity per config entry |
| `__init__.py` | Entry setup/unload/reload; wires `LightControl` + platform |
| `config_flow.py` | `ConfigFlow` (initial setup) + `OptionsFlowHandler` (runtime options) |
| `manifest.json` | HA integration manifest |

## Core logic — read before touching state flags

```
Motion detected
  └─ Light ON   → reset inactivity timer
  └─ Light OFF
       └─ _off_by_integration = True  → _smart_turn_on()
            └─ lux > threshold        → skip, keep flag True (re-check next motion)
            └─ lux ≤ threshold        → turn on, clear flag, start timer
       └─ _off_by_integration = False → do nothing (user turned it off)

Inactivity timer fires (async_call_later, not a poll loop)
  └─ Any sensor still active → restart timer
  └─ All sensors clear       → turn off, set _off_by_integration = True

Light turned OFF event
  └─ by integration → _off_by_integration stays True  (motion will re-trigger)
  └─ by user        → _off_by_integration stays False (motion blocked)

Light turned ON event (any source) → start inactivity timer
```

### `_off_by_integration` invariant

- Set `True` only in `_check_timeout` just before calling `turn_off`
- Cleared to `False` only in `_smart_turn_on` just before calling `turn_on`
- Never touch it in the "user turned off" branch of `_on_light_state_change`
- Keeping it `True` while lux is too high is intentional — allows auto-on as room darkens

## Architecture decisions

**No polling loop.** Timeouts use `async_call_later`. Each motion event cancels the pending callback and schedules a new one. Zero overhead between events.

**`OptionsFlowWithReload`** is used instead of a manual update listener. Saving options triggers a full `async_reload_entry` cycle automatically — no manual attribute patching.

**Per-light automation switch** stored at `hass.data[DOMAIN][CONF_AUTOMATION_ENABLED][light_entity]`. Checked at the top of every motion callback and `_check_timeout`. `None` (switch not yet registered) counts as enabled.

**`initialize()` is idempotent.** Always tears down existing listeners before re-subscribing. Safe to call on reload.

**`unload()` is the single cleanup path.** Cancels `async_call_later`, unsubscribes all listeners. Called from `async_unload_entry` in `__init__.py`.

## Key constants (`const.py`)

```python
DOMAIN = "haas_intelli_lights"
CONF_AUTOMATION_ENABLED = "automation_enabled"   # key in hass.data[DOMAIN]
LIGHT_ENTITY_INPUT_NAME = "light_entity"         # stored in entry.data
MOTION_SENSOR_INPUT_NAME = "motion_sensors"      # stored in entry.options
ILLUMINANCE_SENSOR_INPUT_NAME = "illuminance_sensor"
ILLUMINANCE_THRESHOLD_INPUT_NAME = "illuminance_threshold"
AUTO_OFF_DELAY_INPUT_NAME = "auto_off_delay"     # minutes, float
```

`entry.data` holds only `name` + `light_entity` (immutable after creation).
`entry.options` holds everything else (editable at runtime).

## hass.data layout

```python
hass.data[DOMAIN] = {
    "instances": {
        "light.bedroom": <LightControl>,
        "light.kitchen": <LightControl>,
    },
    "automation_enabled": {
        "light.bedroom": <AutomationEnabledSwitch>,
        "light.kitchen": <AutomationEnabledSwitch>,
    },
}
```

## HA API notes (2024.1+)

- Use `hass.async_create_task()` — not `hass.loop.create_task()`
- `OptionsFlow.__init__` must not take `config_entry`; use `self.config_entry` (injected)
- `EntityCategory` imports from `homeassistant.const`
- `_attr_has_entity_name = True` is required on all new entity classes
- `iot_class` is `"local_push"` for event-driven integrations
- Duplicate entry prevention: use `async_set_unique_id` + `_abort_if_unique_id_configured`

## Common tasks

**Add a new config option**
1. Add constant to `const.py`
2. Add field to `ConfigFlow.async_step_user` schema
3. Add field to `OptionsFlowHandler.async_step_init` schema (pre-fill from `self.config_entry.options`)
4. Read it in `LightControl.__init__` from `config` dict

**Add a new sensor device class**
Update `_ACTIVE_STATES` / `_INACTIVE_STATES` in `light_control.py` and the device_class filter list in `config_flow.py` (`_motion_entities`).

**Change timeout behaviour**
Only edit `_schedule_timeout`, `_cancel_timeout`, and `_check_timeout` in `light_control.py`.
