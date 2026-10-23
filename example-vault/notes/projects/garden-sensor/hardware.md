# Garden sensor hardware

## Parts per node
- ESP32-C3 board, capacitive soil probe v2.0, 18650 cell, 1 W solar panel, TP4056 charger board.
- Total about 14 euros per node.

## Probes
- The cheap resistive probes corroded within three weeks. Capacitive probes only.
- Seal the top edge of the capacitive probe with nail varnish or it wicks water into the electronics.

## Power
- Measured draw: 45 mA awake with Wi-Fi, 12 uA in deep sleep.
- In November the panel gets about 2 hours of usable sun on the balcony, which is not enough for 48 wake-ups a day.
- Options: wake every 60 minutes in winter, or a 2 W panel.
