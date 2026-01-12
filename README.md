# Intelligent Lighting Control for Home Assistant

This Home Assistant custom integration provides intelligent light control based on motion detection. It allows you to automate turning lights on and off based on motion events, while also respecting manual overrides. The integration ensures lights are only turned off if no motion is detected for a configurable time.


## What this does in a nutshell
| Situation | Expected behaviour | 
---------------- | ------------------
| You manually turn the light ON | System starts managing it | 
| You leave the room	| Light auto turns OFF after timeout | 
| You return and it’s still dark | Light turns ON automatically | 
| You return and it’s bright | Light stays OFF | 
| Sun later sets while you are still in the room	| Light turns ON | 
| You manually turn light OFF while in the room	| System should NOT turn it back on | 
| You manually turn light OFF and leave	| It stays OFF forever until you turn it on manually again |  


## Features

- **Motion-based Light Control**: Automatically turns lights on when motion is detected and off when no motion is detected for a defined period.
- **Manual Override Detection**: If the light is manually turned on, it prevents the light from being automatically turned off immediately. If turnef off manually it wont turn on again.
- **Light State Reset**: Resets the timer for each light whenever motion is detected while the light is on.
- **Configurable Auto Off Delay**: Allows you to set the number of minutes (or seconds) after which the light should be turned off when no motion is detected.

## Installation

1. Download the `haas_intelli_lights` custom component and place it in your Home Assistant `custom_components` directory.




