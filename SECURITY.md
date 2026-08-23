# Security Policy

## Supported versions

Security fixes are applied to the latest revision on the default branch. This
project is experimental occupancy sensing software and must not be treated as a
life-safety, alarm, access-control, or identity system.

## Reporting a vulnerability

Do not open a public issue containing credentials, network identifiers, sensor
history, or details that expose a household's routines. Use the repository's
private security-advisory feature. Include reproduction steps with synthetic or
redacted data. Revoke any credential that may have been exposed before sharing
the report.

## Deployment baseline

- Keep Home Assistant, the MQTT broker, and the publisher on a trusted LAN or
  isolated IoT VLAN. Never expose the broker directly to the internet.
- Prefer MQTT Discovery over a Home Assistant long-lived access token.
- Give the publisher a dedicated broker identity with publish-only access to
  its discovery, availability, and state topics. Deny wildcard access to other
  devices.
- Use TLS with broker certificate verification whenever traffic crosses an
  untrusted segment. Restrict plaintext MQTT by host firewall to the exact
  publisher and broker addresses.
- Store credentials outside the repository with owner-only permissions. Do not
  pass secrets as command-line arguments or write them to application logs.
- Discovery configuration and availability may be retained. Motion `ON` and
  passage-event messages must not be retained. Publish `OFF` after startup and
  reconnection, and use a last-will message for offline status.
- Keep the MQTT publisher independent from unrelated services. Broker outages
  must use bounded retry/backoff and must not accumulate an unbounded queue or
  replay expired motion events.
- Do not use this sensor alone to operate locks, alarms, heating safety limits,
  or other physical controls. Require a second independent signal.

## Privacy threat-model checklist

Review this checklist before each public release and deployment:

- [ ] No real address, resident name, account name, hostname, absolute personal
      path, SSID, BSSID, MAC address, IP address, token, password, or certificate
      is committed.
- [ ] Documentation and tests use reserved examples and synthetic sensor data.
- [ ] MQTT topics and Home Assistant entity names do not reveal a household,
      resident, address, or daily routine.
- [ ] Raw RSSI samples remain local unless explicitly required; Home Assistant
      receives throttled summaries rather than a continuous one-second stream.
- [ ] Recorder history and backups have a defined retention period and access
      control appropriate for occupancy data.
- [ ] Logs omit network identifiers and raw event history and rotate with a
      bounded retention period.
- [ ] Motion state is unavailable or `OFF` after publisher/broker failure; stale
      retained `ON` state cannot trigger an automation.
- [ ] A broker outage cannot block collection, exhaust memory/disk, or affect
      unrelated processes.
- [ ] False positives from doors, pets, fans, and moving devices are tested.
- [ ] Alerts and physical automations require rate limits, cooldowns, and an
      independent confirmation source.

## Public-release check

Before publishing, inspect the complete Git history as well as the working tree.
Deleting a secret in a later commit does not remove it from earlier commits.
Rotate exposed credentials and rewrite history before making the repository
public.
