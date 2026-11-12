# Jellyfin for Home Assistant

HACS-compatible custom integration that connects your Jellyfin media server to Home Assistant.

Monitor library size, active viewers, and playback sessions. Control remote clients and trigger library scans.

> This is a custom HACS integration (domain: `jellyfin_ha`). It can be used alongside or instead of the built-in Jellyfin integration.

## Features

- **Config flow** setup with server URL + API key
- **Sensors**: server version, active sessions, watching count, transcoding count, movies / series / episodes / songs / albums / artists, users, libraries
- **Binary sensors**: server online, someone watching
- **Media players**: one entity per active Jellyfin session with play / pause / stop / seek / volume / next / previous
- **Button**: scan all libraries
- **Diagnostics** support for troubleshooting

## Installation

### HACS (recommended)

1. Open **HACS** → **Integrations** → menu (⋮) → **Custom repositories**
2. Add this repository URL as category **Integration**:
   ```text
   https://github.com/chancemcox/Homeassistant-jellyfin
   ```
3. Click **Download**
4. Restart Home Assistant
5. Go to **Settings** → **Devices & services** → **Add integration** → **Jellyfin**

### Manual

1. Copy `custom_components/jellyfin_ha` into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Add the **Jellyfin** integration from the UI

## Configuration

1. In Jellyfin: **Dashboard** → **API Keys** → create a new key (name it e.g. `Home Assistant`)
2. In Home Assistant, start the Jellyfin config flow
3. Enter:
   - **Server URL** — e.g. `http://192.168.1.10:8096` or `https://jellyfin.example.com`
   - **API key** — the key you created
   - **Name** (optional) — display name

The API key user should have permission to view sessions and libraries. Admin keys can also trigger library scans.

## Entities

| Platform | Entity | Description |
| --- | --- | --- |
| Sensor | Server version | Jellyfin version string |
| Sensor | Active sessions | Connected clients |
| Sensor | Watching | Sessions currently playing media |
| Sensor | Transcoding | Sessions that are transcoding |
| Sensor | Movies / Series / Episodes / Songs / Albums / Artists | Library counts |
| Sensor | Users / Libraries | Account and virtual-folder counts |
| Binary sensor | Server online | Connectivity |
| Binary sensor | Someone watching | `on` when at least one session is playing |
| Button | Scan libraries | Triggers a full library refresh |
| Media player | Per session | Playback info and remote control |

Session media players appear while a client is connected and become unavailable when the session ends.

## Example automations

### Notify when someone starts watching

```yaml
automation:
  - alias: Jellyfin someone started watching
    trigger:
      - platform: state
        entity_id: binary_sensor.jellyfin_someone_watching
        to: "on"
    action:
      - service: notify.persistent_notification
        data:
          title: Jellyfin
          message: "Someone started watching on Jellyfin."
```

### Nightly library scan

```yaml
automation:
  - alias: Jellyfin nightly scan
    trigger:
      - platform: time
        at: "03:30:00"
    action:
      - service: button.press
        target:
          entity_id: button.jellyfin_scan_libraries
```

## Requirements

- Home Assistant 2024.11.0 or newer
- Jellyfin Server 10.8+ (tested against current stable API)
- HACS (for HACS install path)

## Support

- Issues: [GitHub Issues](https://github.com/chancemcox/Homeassistant-jellyfin/issues)
- Jellyfin docs: https://jellyfin.org/docs/

## License

MIT
