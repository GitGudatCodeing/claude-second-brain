# Garden sensor firmware

## Build
- PlatformIO with the Arduino framework. `pio run -t upload` with the board on USB.
- Wi-Fi and MQTT credentials come from a git-ignored `secrets.h`.

## Calibration
- Read the probe in air (dry value) and in a glass of water (wet value); map linearly to 0 to 100%.
- Each probe differs by up to 15%, so calibrate every probe on its own and store the values per node ID.

## Gotchas
- Wi-Fi connect sometimes takes 8 seconds after deep sleep; a static IP brought it down to under 1 second.
- Publish with QoS 1 and wait for the PUBACK before sleeping, or the last reading is lost.
