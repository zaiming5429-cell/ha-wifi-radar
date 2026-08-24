# Portable RSSI collector

This collector turns the signal strength of the Wi-Fi link used by the host into privacy-safe motion-candidate data for the Home Assistant bridge.

It does not read traffic, identify people, or store SSID, BSSID, MAC, IP address, credentials, or packet contents.

## Supported sources

- WSL2 connected through the Windows Wi-Fi adapter: automatic `netsh.exe` reader
- Native Windows Python: `netsh` reader
- Linux with a supported Wi-Fi adapter: `iw` reader
- Routers and unusual adapters: custom executable that prints JSON

A Wi-Fi receiver must exist on the machine running the collector. Ethernet-only hosts and most Home Assistant appliances cannot measure RSSI without another receiver or a custom router adapter.

## Quick test

```bash
python3 collector/wifi_radar_collector.py --doctor
```

A successful result contains `ok`, the selected source, and the current RSSI. Network identifiers are omitted.

## Run

```bash
python3 collector/wifi_radar_collector.py \
  --output runtime/wifi_radar.json \
  --interval 1
```

The first 20 samples calibrate the moving baseline. Walk through the radio path only after calibration. A candidate also requires at least 4 dB of span and 6 dB of cumulative movement in the recent eight-sample waveform; this rejects small driver/RF step changes that remain elevated for several seconds.

### Linux

Install the operating-system package that provides `iw`, then either allow auto-detection or name the interface:

```bash
python3 collector/wifi_radar_collector.py \
  --source linux \
  --interface wlan0 \
  --output runtime/wifi_radar.json
```

### Custom router or adapter

Provide an executable command without shell operators. It must print one JSON object per invocation:

```json
{"rssi_dbm":-61.5,"signal_percent":77}
```

```bash
python3 collector/wifi_radar_collector.py \
  --source custom \
  --command "/path/to/private-reader --json" \
  --output runtime/wifi_radar.json
```

Keep router credentials in the private reader environment or credential store. Never put them in this repository or command output.

## Limitations

RSSI is a coarse disturbance signal. Hardware, driver, access point, channel width, roaming, doors, pets, appliances, and interference affect it. CSI-grade sensing requires compatible hardware and is outside this project.
