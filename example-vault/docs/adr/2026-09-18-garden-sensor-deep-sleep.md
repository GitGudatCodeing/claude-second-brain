---
status: accepted
date: 2026-09-18
entities: [garden-sensor]
---

# ADR: Deep sleep between readings, interval set by season

## Context
Awake draw is 45 mA, deep sleep 12 uA. With 48 readings a day the node is awake about 6 minutes a day. In winter the 1 W panel does not refill the cell.

## Decision
Deep sleep between readings. Every 30 minutes from April to September, every 60 minutes from October to March. The interval is a retained MQTT message, so it changes without reflashing.

## Options considered
- Light sleep: keeps Wi-Fi associated, but draws about 1 mA, 80x more.
- Fixed 30-minute interval with a 2 W panel: simpler firmware, costs more and the bigger panel does not fit the railing.

## Consequences
- Half the winter readings. Soil moisture changes slowly, so this is fine.
- Firmware must read the retained interval on every wake.
