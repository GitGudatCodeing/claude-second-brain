# Home network

## Layout
- ISP fibre router in bridge mode, then a small OpenWrt router.
- Raspberry Pi 4 on the shelf runs Mosquitto (MQTT broker), Pi-hole and nightly backups.
- IoT devices sit on their own VLAN (VLAN 30) with no route to the laptop network.

## Addresses
- Pi: static lease 192.168.30.2.
- Printer: 192.168.1.40.

## Backups
- restic to an external SSD every night at 02:00, and weekly to a cloud bucket.
- Test a restore on the first Sunday of each month.
