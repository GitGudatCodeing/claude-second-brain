# Lessons

Sample lessons for the eval (fictional). In a real vault this file is written by `scripts/learn.py`.

## L-0001 · 2026-09-14 · active
**Lesson:** Use capacitive soil probes only; resistive probes corrode within weeks in wet soil.
**Cause:** The tomato planter's resistive probe read 0% after three weeks; the copper had corroded.
**Detect:** A probe reading that drifts toward 0% while the soil is visibly wet.
**Tags:** garden-sensor, hardware

## L-0002 · 2026-09-28 · active
**Lesson:** Before an ESP32 goes back to deep sleep, wait for the MQTT PUBACK of its last QoS 1 message.
**Cause:** The chilli node slept right after publish, so the broker never received about a third of the readings.
**Detect:** Gaps in the dashboard at regular wake times while the node's battery is fine.
**Tags:** garden-sensor, firmware, mqtt

## L-0003 · 2026-10-02 · active
**Lesson:** Give every sensor node a static IP; DHCP after deep sleep added up to 8 seconds of awake time.
**Cause:** Each wake waited for a DHCP lease from the router.
**Detect:** Awake time per reading above 2 seconds in the serial log.
**Tags:** garden-sensor, network, power

## L-0004 · 2026-10-12 · active
**Lesson:** Test a restore from backup monthly; a backup that was never restored is a guess.
**Cause:** A colleague lost a month of data because their backup job had silently written empty archives.
**Detect:** No restore test logged in the daily notes for more than five weeks.
**Tags:** backups, home-network

## L-0005 · 2026-10-15 · active
**Lesson:** Keep recipe quantities in the unit the card used and convert only for display.
**Cause:** Converting cups to grams on import changed grandmother's tart and the family noticed.
**Detect:** A migration or import step that rewrites the quantity or unit columns.
**Tags:** recipe-box, data
