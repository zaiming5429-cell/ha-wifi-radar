# WSL2 NAT deployment

This guide exposes the Wi-Fi radar HTTP bridge from WSL2 NAT to one Home Assistant server on the local network. All addresses below are placeholders. Do not publish the bridge on the internet, add it to DuckDNS, or place a real API key in source control.

## 1. Create a protected API key file in WSL2

Generate a long random value using your preferred secret-management method, save only the value in a local file, and restrict it to the service account:

```bash
install -d -m 700 /PATH/TO/PRIVATE_CONFIG
chmod 600 /PATH/TO/PRIVATE_CONFIG/wifi-radar-api-key
```

The key file must not be committed. Verify its permissions without printing its contents:

```bash
stat -c '%a %n' /PATH/TO/PRIVATE_CONFIG/wifi-radar-api-key
```

Expected mode: `600`.

## 2. Run the bridge on the WSL2 interface

LAN access must be explicitly enabled with `--bind 0.0.0.0`. The source path is also explicit:

```bash
python3 /PATH/TO/bridge/wifi_radar_bridge.py \
  --source /PATH/TO/wifi_radar.json \
  --api-key-file /PATH/TO/PRIVATE_CONFIG/wifi-radar-api-key \
  --bind 0.0.0.0 \
  --port 8765
```

Test inside WSL2 without displaying the key:

```bash
curl --fail --silent \
  --header "Authorization: Bearer $(< /PATH/TO/PRIVATE_CONFIG/wifi-radar-api-key)" \
  http://127.0.0.1:8765/health
```

## 3. Optional PM2 service

Use a local ecosystem file containing paths only. Keep the key itself out of the PM2 file and process arguments:

```javascript
module.exports = {
  apps: [{
    name: "wifi-radar-ha-bridge",
    script: "/PATH/TO/bridge/wifi_radar_bridge.py",
    interpreter: "python3",
    args: [
      "--source", "/PATH/TO/wifi_radar.json",
      "--api-key-file", "/PATH/TO/PRIVATE_CONFIG/wifi-radar-api-key",
      "--bind", "0.0.0.0",
      "--port", "8765"
    ],
    autorestart: true,
    max_restarts: 10
  }]
};
```

Start it from WSL2:

```bash
pm2 start /PATH/TO/ecosystem.config.cjs
pm2 status wifi-radar-ha-bridge
```

## 4. Find the current WSL2 address

Run in WSL2 and map the result to `<WSL_IP>` in the commands below:

```bash
hostname -I
```

WSL2 NAT addresses can change after WSL or Windows restarts. Update the port proxy whenever `<WSL_IP>` changes.

## 5. Configure Windows port forwarding

Open **Windows PowerShell as Administrator**. Replace placeholders before running the commands:

```powershell
netsh interface portproxy add v4tov4 `
  listenaddress=<WINDOWS_LAN_IP> listenport=8765 `
  connectaddress=<WSL_IP> connectport=8765
```

Confirm the mapping:

```powershell
netsh interface portproxy show v4tov4
```

Create a firewall rule restricted to the Home Assistant server only:

```powershell
New-NetFirewallRule `
  -DisplayName "WiFi Radar HA Bridge" `
  -Direction Inbound `
  -Action Allow `
  -Protocol TCP `
  -LocalAddress <WINDOWS_LAN_IP> `
  -LocalPort 8765 `
  -RemoteAddress <HA_SERVER_IP> `
  -Profile Private
```

Do not use `Any` for `-RemoteAddress`, and do not create a router port-forwarding rule.

## 6. Connectivity tests

On Windows, confirm that the forwarded listener is reachable:

```powershell
Test-NetConnection -ComputerName <WINDOWS_LAN_IP> -Port 8765
```

From the Home Assistant host, request the authenticated health endpoint using its locally stored secret:

```bash
curl --fail --silent \
  --header "Authorization: Bearer <API_KEY_FROM_LOCAL_SECRET_STORE>" \
  http://<WINDOWS_LAN_IP>:8765/health
```

Use `http://<WINDOWS_LAN_IP>:8765/api/v1/state` for the sensor state. The bridge is intended only for the trusted local network link between `<HA_SERVER_IP>` and `<WINDOWS_LAN_IP>`.

## 7. Update the port proxy after a WSL2 address change

In Administrator PowerShell, delete the old mapping and add it again with the new `<WSL_IP>`:

```powershell
netsh interface portproxy delete v4tov4 `
  listenaddress=<WINDOWS_LAN_IP> listenport=8765

netsh interface portproxy add v4tov4 `
  listenaddress=<WINDOWS_LAN_IP> listenport=8765 `
  connectaddress=<WSL_IP> connectport=8765
```

The existing firewall rule remains limited to `<HA_SERVER_IP>`. Re-run `Test-NetConnection` after updating the proxy.

## 8. Remove LAN exposure

In Administrator PowerShell:

```powershell
netsh interface portproxy delete v4tov4 `
  listenaddress=<WINDOWS_LAN_IP> listenport=8765

Remove-NetFirewallRule -DisplayName "WiFi Radar HA Bridge"
```

Then stop the WSL2 process if it is no longer needed:

```bash
pm2 stop wifi-radar-ha-bridge
```

Verify removal:

```powershell
netsh interface portproxy show v4tov4
Test-NetConnection -ComputerName <WINDOWS_LAN_IP> -Port 8765
```
