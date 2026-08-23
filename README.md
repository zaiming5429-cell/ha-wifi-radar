# Wi-Fi Radar for Home Assistant

Home Assistant custom integration for a local Wi-Fi RSSI radar bridge. It polls
one authenticated JSON endpoint and exposes a passage candidate, RSSI,
vibration score, bridge status, and the latest merged passage duration.

> This is a radio-path disturbance indicator, not a person-identification,
> occupancy, life-safety, or certified security sensor. Doors, pets, moving
> objects, interference, and Wi-Fi changes can produce similar signals.

## Requirements

- Home Assistant with network access to the bridge
- A Wi-Fi Radar bridge exposing `GET /api/v1/state`
- An API key configured on that bridge

Expected response:

```json
{
  "available": true,
  "source_updated_at": "2026-01-01T12:00:00+00:00",
  "current": {
    "rssi_dbm": -58,
    "vibration_score": 79,
    "motion_level": "high"
  },
  "passage": {
    "active": true,
    "last": {
      "duration_seconds": 7.2
    }
  }
}
```

The API key is sent as `Authorization: Bearer <API_KEY>`. Do not place
credentials, SSID, BSSID, MAC addresses, or personal data in the response.

## Installation with HACS

1. In HACS, open **Integrations** and choose **Custom repositories**.
2. Add your public repository URL and select the **Integration** category.
3. Install **Wi-Fi Radar**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration** and search for
   **Wi-Fi Radar**.

Public repository: `https://github.com/zaiming5429-cell/ha-wifi-radar`.

## Manual installation

Copy `custom_components/wifi_radar` into your Home Assistant configuration
directory:

```text
<config>/custom_components/wifi_radar/
```

Restart Home Assistant, then add the integration from **Settings → Devices &
services**.

## Configuration

The setup form requests:

- **Bridge URL**: base URL such as `http://wifi-radar-bridge.local:8080`
- **API key**: displayed as a password and never written to integration logs
- **Name**: Home Assistant device name
- **Scan interval**: 1–60 seconds; 2 seconds by default

The URL must use HTTP or HTTPS and must not contain embedded credentials, a
query string, or a fragment. Prefer HTTPS on untrusted networks and restrict the
bridge to your local network.

## Entities

- Passage candidate binary sensor (`motion`)
- RSSI sensor (`dBm`)
- Vibration score sensor (`%`, 0–100 expected)
- Status sensor (`calibrating`, `stable`, `watch`, `moving`, `stale`)
- Last passage duration sensor (`s`)

All entities share one coordinator request per interval. If polling fails, the
entities become unavailable. The bridge URL and API key are redacted from Home
Assistant diagnostics.

## Privacy and security

- Use a dedicated, randomly generated API key.
- Do not expose the bridge directly to the public internet.
- Do not commit real URLs, tokens, SSIDs, MAC addresses, or captured radio data.
- Treat passage events as candidates and validate automations against real-world
  false positives before enabling alerts.

## License

MIT
