# Garden sensor

## What
- A soil-moisture sensor in each of the three balcony planters (tomatoes, chillies, herbs).
- Readings every 30 minutes go to the Pi over MQTT; a small dashboard shows the last 7 days.
- A phone notification when a planter drops below 30% moisture.

## Status
- Two of three nodes running since 2026-09-20. The herbs node is waiting for a replacement probe.
- Battery life is the open problem; see hardware notes.

## Links
- Decisions: MQTT over HTTP, deep sleep between readings.
