# MQTT Busylight Controller for Kuando HID Busylights

## Overview

This project provides a simple and straightforward MQTT-based controller for Kuando HID-based Busylights (Alpha and Omega). 
The controller allows for color control, blinking, fading, and ringtone triggers through MQTT messages.

## Features

- Control Kuando Busylights via MQTT.
- Support for setting solid colors, blinking lights, and fading effects.
- Control various ringtones on the Busylight.
- Keep-alive mechanism to ensure the device stays active.
- Ability to execute custom raw color commands.

## Hardware Requirements

- Kuando Busylight UC Omega or Alpha.
- HID library support for USB communication.

## Software Requirements

- Python 3.x
- `hid` library for USB communication
- `paho-mqtt` library for MQTT communication

## Installation

1. Install the required Python libraries:
    ```bash
    pip install hid paho-mqtt
    ```

2. Clone or download the repository and navigate to the project directory.

## Usage

### Running the Controller

To run the controller, execute the script:

```bash
python busylight_controller.py
```

### MQTT Control

Connect to your MQTT broker and send messages to control the Busylight. The MQTT topic to subscribe to is `busylight/control`.

#### Example Commands

- Set Colors:
    - `color_red`
    - `color_green`
    - `color_blue`
    - `color_yellow`
    - `color_cyan`
    - `color_magenta`
    - `color_white`
    - `color_orange`
    - `color_purple`
    - `color_pink`
    - `color_brown`

- Blink Colors:
    - `blink_color_red`
    - `blink_color_green`
    - `blink_color_blue`
    - `blink_color_yellow`
    - `blink_color_cyan`
    - `blink_color_magenta`
    - `blink_color_white`
    - `blink_color_orange`
    - `blink_color_purple`
    - `blink_color_pink`
    - `blink_color_brown`

- Ringtones:
    - `ring_off`
    - `ring_open_office`
    - `ring_quiet`
    - `ring_funky`
    - `ring_fairy_tale`
    - `ring_kuando_train`
    - `ring_telephone_nordic`
    - `ring_telephone_original`
    - `ring_telephone_pick_me_up`
    - `ring_buzz`

- Other Commands:
    - `off` - Turn off the light.
    - `rainbow_on` - Start rainbow cycling.
    - `rainbow_off` - Stop rainbow cycling.
    - `fade_red`, `fade_green`, `fade_blue`, etc. - Start color fading.
    - `fade_off` - Stop color fading.
    - `raw_color 255,0,0` - Set custom raw color.
    - `reset_device` - Reset the device.
    - `device_bootloader` - Start bootloader mode.

### Stopping the Controller

The script can be stopped by pressing `Ctrl+C` in the terminal. This will ensure the device is properly turned off and closed.

## Code Structure

- **Main script**: Initializes the device, sets up the MQTT client, and starts the keep-alive thread.
- **Helper functions**: Handle sending commands to the Busylight device.
- **MQTT callbacks**: Process incoming MQTT messages and execute appropriate commands.
- **Thread management**: Manages threads for rainbow cycling, fading, and keep-alive functionalities.

## License

This project is licensed under the MIT License. See the LICENSE file for details.