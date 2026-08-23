# Wi-Fi Radar Home Assistant HTTP Bridge

This standard-library-only service reads a collector JSON file without modifying it and exposes an authenticated local API.

## API

- `GET /api/v1/state`: current RSSI, vibration score, availability, and merged passage session
- `GET /health`: `200` when the source is fresh, otherwise `503`
- Both endpoints require `Authorization: Bearer <key>`.

By default, a passage starts after two consecutive scores of at least 45 and ends after three consecutive scores below 35. Tune this per installation with `--start-score`, `--end-score`, `--start-samples`, and `--end-samples`. The response includes peak score, duration, and maximum RSSI deviation from the collector baseline. Only the current and latest completed passage are retained.

## Run

The source path is intentionally mandatory and the API binds only to loopback by default.

```bash
python3 wifi_radar_bridge.py \
  --source /PATH/TO/wifi_radar.json \
  --api-key-file /PATH/TO/PRIVATE_CONFIG/api_key \
  --bind 127.0.0.1 \
  --port 8765
```

For a Home Assistant host on the LAN, explicitly set `--bind 0.0.0.0`, restrict the port with the host firewall to the Home Assistant IP, and use a long random key. Do not put the key on the command line; use the environment or a permission-restricted `--api-key-file`.

Example request:

```bash
curl --header "Authorization: Bearer $(< /PATH/TO/PRIVATE_CONFIG/api_key)" http://127.0.0.1:8765/api/v1/state
```

## PM2 example

Create a local ecosystem file that references a permission-restricted key file, then use placeholders similar to:

```javascript
module.exports = { apps: [{
  name: "wifi-radar-ha-bridge",
  script: "/PATH/TO/wifi_radar_bridge.py",
  interpreter: "python3",
  args: "--source /PATH/TO/wifi_radar.json --api-key-file /PATH/TO/PRIVATE_CONFIG/api_key --bind 127.0.0.1 --port 8765"
}] };
```

Do not commit a real key. For LAN access under WSL2, verify the Windows firewall and WSL networking mode/port forwarding separately.

## Test

```bash
python3 -m unittest -v test_wifi_radar_bridge.py
```
