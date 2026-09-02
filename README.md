# Wi-Fi Radar for Home Assistant

A complete, privacy-first pipeline that measures Wi-Fi RSSI variation on a receiver, derives motion candidates, serves them through an authenticated local API, and registers them as Home Assistant entities.

> This is a radio-path disturbance indicator, not person identification, certified occupancy, life-safety, or security equipment. Doors, pets, appliances, roaming, interference, and network changes can produce similar signals.

## Architecture

```text
Wi-Fi access point or router
          ⇅ normal Wi-Fi link
Windows, WSL2, or Linux receiver
  collector/wifi_radar_collector.py
          ↓ private runtime JSON
  bridge/wifi_radar_bridge.py
          ↓ authenticated local HTTP
Home Assistant custom integration
```

The router does not need a vendor cloud API. The receiving computer measures its own connected-link RSSI. A server connected only by Ethernet needs a compatible Wi-Fi receiver or a custom RSSI reader.

## Supported environments

- WSL2 using the Windows host Wi-Fi adapter (`netsh.exe`)
- Native Windows Python (`netsh`)
- Linux Wi-Fi adapters supported by `iw`
- Other routers and receivers through a private custom executable that prints `rssi_dbm` JSON

macOS and Ethernet-only systems are not automatically supported because they may not expose continuous RSSI. Use the custom adapter contract when a platform or router provides its own API.

## End-to-end quick start

Clone the repository on the receiver and run the hardware check:

```bash
git clone https://github.com/zaiming5429-cell/ha-wifi-radar.git
cd ha-wifi-radar
python3 collector/wifi_radar_collector.py --doctor
```

Start collection. Runtime files are gitignored and created with mode `600`:

```bash
python3 collector/wifi_radar_collector.py \
  --output runtime/wifi_radar.json \
  --interval 1
```

In another terminal, generate a private API key. The helper stores it with mode `600` and does not print its value:

```bash
python3 tools/generate_api_key.py runtime/api_key
``` Then start the bridge:

```bash
python3 bridge/wifi_radar_bridge.py \
  --source runtime/wifi_radar.json \
  --api-key-file runtime/api_key \
  --bind 0.0.0.0 \
  --port 8765
```

Test locally without printing the key:

```bash
curl --fail --silent \
  --header "Authorization: Bearer $(< runtime/api_key)" \
  http://127.0.0.1:8765/health
```

Do not expose port 8765 through the internet or router port forwarding. WSL2 users should follow [the WSL2 deployment guide](docs/WSL2_DEPLOYMENT.md). Detailed collector options and the custom adapter contract are in [the collector guide](collector/README.md).

## Home Assistant installation with HACS

1. In HACS, open **Integrations** and choose **Custom repositories**.
2. Add `https://github.com/zaiming5429-cell/ha-wifi-radar` as an **Integration**.
3. Install **Wi-Fi Radar** and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration → Wi-Fi Radar**.
5. Enter the receiver LAN bridge URL and the private API key.

For manual installation, copy `custom_components/wifi_radar` into `<config>/custom_components/wifi_radar` and restart Home Assistant.

## Home Assistant entities

The integration keeps polling the bridge for availability, but suppresses
quiet RSSI/score jitter. Home Assistant entity updates are published once when
a passage starts and once when it ends.

- Passage candidate binary sensor
- RSSI sensor in dBm
- Vibration score from 0 to 100 percent
- Status sensor: calibrating, stable, watch, moving, or stale
- Latest merged passage duration in seconds

The integration performs one authenticated request per interval. Credentials are password fields, never added to logs, and redacted from diagnostics.

## How detection works

The collector maintains a rolling baseline from the last 120 RSSI samples and combines instantaneous change, baseline deviation, and short-window volatility. The first 20 readings are calibration. A motion candidate requires consecutive elevated scores plus a recent waveform span of at least 4 dB and cumulative movement of at least 6 dB. This suppresses small RSSI step changes that remain elevated for several seconds. The bridge merges only collector-confirmed readings into a passage event.

Placement and environment matter more than universal thresholds. Position the receiver so the monitored path lies between the access point and receiver, allow calibration while the area is quiet, and validate false positives before using automations.

## Privacy and security

- No packets or user traffic are captured.
- SSID, BSSID, MAC, IP address, router credentials, and HA credentials are not written to radar output.
- Runtime JSON and API key files are excluded from Git and should remain mode `600`.
- The API requires a Bearer key of at least 16 characters and compares it in constant time.
- Restrict the bridge firewall rule to the HA host or trusted local subnet.
- Never publish the API through DuckDNS or a router port-forward.

## Validation

GitHub Actions runs collector and bridge tests, a private-identifier scan, HACS validation, and Home Assistant hassfest validation on every push.

## License

MIT
