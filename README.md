# Intelligent Lighting Control for Home Assistant

A Home Assistant custom integration that provides smart, event-driven light automation based on motion sensors, presence detectors, and door/window contacts. Designed for instant reaction with minimal resource usage.

## How it works

| Situation | Behaviour |
|-----------|-----------|
| You manually turn the light ON | Integration starts managing it — starts the inactivity timer |
| You leave the room | Light auto-turns OFF after the configured timeout |
| You return while it's dark | Light turns ON automatically |
| You return while it's bright (above lux threshold) | Light stays OFF |
| You keep moving as it gets darker | Light turns ON once lux drops below threshold |
| You manually turn the light OFF while in the room | Integration will NOT turn it back on, even on motion |
| You manually turn the light OFF and leave | Stays OFF forever until you turn it on manually again |
| You walk out through an adjacent area (exit sensor) | Timer switches to the shorter exit delay |
| You come back before the exit timer expires | Timer resets to the normal delay |
| Automation is paused via the per-light switch | All motion/timeout logic is suspended for that light only |

## Features

- **Event-driven** — reacts instantly to state changes; no polling loop
- **Precise timeout** — inactivity timer fires at exactly the configured delay, not on a poll interval
- **Manual override detection** — distinguishes user off vs automation off; respects user intent
- **Illuminance gating** — only turns on when lux is below a configurable threshold; re-evaluates on every motion event as the room gets darker; fails open when sensor is unavailable
- **Exit-sensor acceleration** — optional neighbouring sensors (hallway, door) shorten the timeout when you leave, without affecting rooms you're still in
- **Per-light automation switch** — pause one room's automation without affecting others; entity ID is `switch.<light_name>_automation_enabled`
- **Multi-sensor support** — multiple motion/occupancy/door/window sensors per light, any active sensor resets the timer
- **Safe options reload** — changing any option triggers a clean reload with no listener leaks
- **Hot reload service** — `haas_intelli_lights.reload` flushes the module cache and reloads all entries without restarting HA

## Supported sensor device classes

`motion` · `occupancy` · `door` · `window` · `tamper`

Active states recognised: `on`, `open`, `detected`, `occupied`

## Installation via HACS

1. HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/artin961/haas_intelli_lights` — type **Integration**
3. Install **Intelligent Lighting**
4. Restart Home Assistant
5. Settings → Devices & Services → Add Integration → search **Intelligent Lighting**

## Manual installation

1. Copy `custom_components/homeassistant_inteligent_ights/` into your HA `custom_components/` directory
2. Restart Home Assistant
3. Settings → Devices & Services → Add Integration → search **Intelligent Lighting**

## Configuration

Each configured entry controls one light. Add multiple entries for multiple lights.

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| Name | Yes | — | Friendly name for this automation entry |
| Light entity | Yes | — | The light to control |
| Motion sensors | No | — | One or more binary sensors to watch |
| Auto-off delay (min) | Yes | 5 | Inactivity timeout before turning off (0–300) |
| Illuminance sensor | No | — | Lux sensor to gate turn-on |
| Illuminance threshold (lux) | No | 0 | Light only turns on when lux ≤ this value |
| Exit sensors | No | — | Neighbouring sensors (hallway PIR, door) that signal you are leaving |
| Exit delay (min) | No | 1 | Short timeout used after an exit sensor fires (0–60) |

All options except the light entity can be changed at runtime via **Configure** on the integration entry — the entry reloads automatically.

## Exit sensor logic

Exit sensors let the integration distinguish "still in the room" from "just left". Configure a hallway PIR or adjacent room sensor as an exit sensor for a given light.

**When an exit sensor fires:**
- If room motion occurred within the last `exit_delay` minutes → ignored (you are still in the room, or someone just passed through)
- Otherwise → the current timer is cancelled and restarted at `exit_delay` — the light turns off sooner

**When room motion fires while the exit timer is running:**
- Timer resets back to the full `auto_off_delay` — you came back

**Example setup — kitchen:**
- Motion sensor: `binary_sensor.kitchen_pir`
- Auto-off delay: 10 min
- Exit sensor: `binary_sensor.hallway_pir`
- Exit delay: 1 min

Sitting at the table → 10 min timeout resets on every movement. Walking to the living room via the hallway → hallway PIR fires, kitchen switches to 1 min timer. If you come back within 1 min, full 10 min timer restores. If someone else walks through the hallway while you are still in the kitchen → kitchen PIR fired recently, hallway trigger is ignored.

## Per-light automation switch

Every configured entry exposes an **Automation Enabled** switch in the CONFIG category. The entity ID is `switch.<light_object_id>_automation_enabled` (e.g. `switch.bedroom_automation_enabled`). Turning it off suspends all motion and timeout logic for that light without removing the configuration.

## Hot reload (no HA restart)

After editing integration files on the HA host, call the reload service to apply changes immediately:

```yaml
service: haas_intelli_lights.reload
```

Available in Developer Tools → Services. Flushes the Python module cache and reloads all config entries.

## Logic detail

```
Motion detected
  └─ Light is ON  →  reset inactivity timer (normal delay)
  └─ Light is OFF
       └─ off_by_integration = True  →  smart_turn_on()
            └─ lux > threshold            →  skip (re-check on next motion)
            └─ lux ≤ threshold, or no     →  turn on, start timer
               sensor / unavailable
       └─ off_by_integration = False  →  do nothing (user turned it off)

Exit sensor fires
  └─ Light OFF                        →  ignore
  └─ Room motion < exit_delay ago     →  ignore (still in room)
  └─ Otherwise                        →  restart timer at exit_delay

Inactivity timer fires
  └─ Any room sensor still active  →  restart timer (normal delay)
  └─ All sensors clear             →  turn off, set off_by_integration = True

Light turned OFF
  └─ by integration  →  keep off_by_integration = True
  └─ by user         →  off_by_integration stays False (blocks auto re-trigger)

Light turned ON (any source)  →  start inactivity timer (normal delay)
```

## Requirements

- Home Assistant 2024.1.0 or newer
- Python 3.12+
