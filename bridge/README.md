# Wi-Fi Radar Home Assistant HTTP Bridge

This standard-library-only service reads a collector JSON file without modifying it and exposes an authenticated local API.

## API

- `GET /api/v1/state`: current RSSI, vibration score, availability, and merged passage session
- `GET /health`: `200` when the source is fresh, otherwise `503`
- Both endpoints require `Authorization: Bearer <key>`.

A passage starts after two consecutive scores of at least 45 and ends after three consecutive scores below 35. The response includes peak score, duration, and maximum RSSI deviation from the collector baseline. Only the current and latest completed passage are retained.

## Run

The source path is intentionally mandatory and the API binds only to loopback by default.

```bash
export WIFI_RADAR_API_KEY='REPLACE_WITH_A_LONG_RANDOM_SECRET'
python3 wifi_radar_bridge.py \
  --source /PATH/TO/wifi_radar.json \
  --bind 127.0.0.1 \
  --port 8765
```

For a Home Assistant host on the LAN, explicitly set `--bind 0.0.0.0`, restrict the port with the host firewall to the Home Assistant IP, and use a long random key. Do not put the key on the command line; use the environment or a permission-restricted `--api-key-file`.

Example request:

```bash
curl -H "Authorization: Bearer $WIFI_RADAR_API_KEY" http://127.0.0.1:8765/api/v1/state
```

## PM2 example

Create a local ecosystem file that injects `WIFI_RADAR_API_KEY` from your secret-management method, then use placeholders similar to:

```javascript
module.exports = { apps: [{
  name: "wifi-radar-ha-bridge",
  script: "/PATH/TO/wifi_radar_bridge.py",
  interpreter: "python3",
  args: "--source /PATH/TO/wifi_radar.json --bind 127.0.0.1 --port 8765",
  env: { WIFI_RADAR_API_KEY: "LOAD_FROM_SECRET_STORE" }
}] };
```

Do not commit a real key. For LAN access under WSL2, verify the Windows firewall and WSL networking mode/port forwarding separately.

## Test

```bash
python3 -m unittest -v test_wifi_radar_bridge.py
```
