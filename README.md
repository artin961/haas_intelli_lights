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
| Automation is paused via the per-light switch | All motion/timeout logic is suspended for that light only |

## Features

- **Event-driven** — reacts instantly to state changes; no polling loop
- **Precise timeout** — inactivity timer fires at exactly the configured delay, not on a poll interval
- **Manual override detection** — distinguishes user off vs automation off; respects user intent
- **Illuminance gating** — only turns on when lux is below a configurable threshold; re-evaluates on every motion event as the room gets darker
- **Per-light automation switch** — pause one room's automation without affecting others (appears in each entry's settings)
- **Multi-sensor support** — multiple motion/occupancy/door/window sensors per light, any active sensor resets the timer
- **Safe options reload** — changing any option triggers a clean reload with no listener leaks

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

Each configured entry controls one light. You can add multiple entries for multiple lights.

| Field | Required | Description |
|-------|----------|-------------|
| Name | Yes | Friendly name for this automation entry |
| Light entity | Yes | The light to control |
| Motion sensors | No | One or more binary sensors to watch |
| Auto-off delay (minutes) | Yes | Inactivity timeout before turning off (0–300 min) |
| Illuminance sensor | No | Lux sensor to gate turn-on |
| Illuminance threshold (lux) | No | Light only turns on when lux is at or below this value |

All options except the light entity can be changed at runtime via **Configure** on the integration entry — the entry reloads automatically.

## Per-light automation switch

Every configured entry exposes an **Automation Enabled** switch in the CONFIG category. Turning it off suspends all motion and timeout logic for that light without removing the configuration.

## Logic detail

```
Motion detected
  └─ Light is ON  →  reset inactivity timer
  └─ Light is OFF
       └─ off_by_integration = True  →  smart_turn_on()
            └─ illuminance > threshold  →  skip (re-check on next motion)
            └─ illuminance ≤ threshold (or no sensor)  →  turn on, start timer
       └─ off_by_integration = False  →  do nothing (user turned it off)

Inactivity timer fires
  └─ Any sensor still active  →  restart timer
  └─ All sensors clear        →  turn off, set off_by_integration = True

Light turned OFF
  └─ by integration  →  keep off_by_integration = True
  └─ by user         →  off_by_integration stays False  (blocks auto re-trigger)

Light turned ON (any source)  →  start inactivity timer
```

## Requirements

- Home Assistant 2024.1.0 or newer
- Python 3.12+
