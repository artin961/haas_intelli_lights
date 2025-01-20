# Intelligent Lighting Control for Home Assistant

This Home Assistant custom integration provides intelligent light control based on motion detection. It allows you to automate turning lights on and off based on motion events, while also respecting manual overrides. The integration ensures lights are only turned off if no motion is detected for a configurable time.

## Features

- **Motion-based Light Control**: Automatically turns lights on when motion is detected and off when no motion is detected for a defined period.
- **Manual Override Detection**: If the light is manually turned on, it prevents the light from being automatically turned off immediately. If turnef off manually it wont turn on again.
- **Light State Reset**: Resets the timer for each light whenever motion is detected while the light is on.
- **Configurable Auto Off Delay**: Allows you to set the number of minutes (or seconds) after which the light should be turned off when no motion is detected.

## Installation

1. Download the `haas_intelli_lights` custom component and place it in your Home Assistant `custom_components` directory.

2. Add the configuration to your `configuration.yaml` file:

```yaml
haas_intelli_lights:
  lights:
    light.living_room:
      motion_sensor: binary_sensor.motion_living_room
      auto_off_delay: 5  # Minutes
    light.bedroom:
      motion_sensor: binary_sensor.motion_bedroom
      auto_off_delay: 10  # Minutes
