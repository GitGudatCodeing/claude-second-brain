---
status: accepted
date: 2026-09-10
entities: [garden-sensor, home-network]
---

# ADR: Garden sensor sends readings over MQTT, not HTTP

## Context
Nodes wake, read the probe, send one value and sleep. Every second awake costs battery. The Pi already runs a broker for other devices.

## Decision
Publish readings to Mosquitto on the Pi with QoS 1, topic `garden/<node-id>/moisture`.

## Options considered
- MQTT: small packets, persistent session, broker already running. Needs the broker to be up.
- HTTP POST to a tiny API: easy to debug with curl, but TLS handshakes and headers kept the radio on about 3x longer in a test.
- ESP-NOW to a gateway node: lowest power, but one more device to build and power.

## Consequences
- The dashboard subscribes to the same topics; no API to maintain.
- If the Pi is down, readings are lost. Acceptable for plants.
