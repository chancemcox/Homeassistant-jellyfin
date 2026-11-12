# Jellyfin for Home Assistant

This repository includes:

1. **Jellyfin Server add-on** — installs and runs Jellyfin on Home Assistant OS (port **8096**)
2. **HACS integration** (`jellyfin_ha`) — connects Home Assistant to that Jellyfin server

> The integration does not install Jellyfin by itself. On HA OS, use the add-on below first.

## Install Jellyfin Server (Home Assistant OS)

1. **Settings → Add-ons → Add-on store**
2. ⋮ → **Repositories** → add:
   ```text
   https://github.com/chancemcox/Homeassistant-jellyfin
   ```
3. Install **Jellyfin Server** → **Start**
4. Open the add-on **Web UI** (or `http://homeassistant.local:8096`)
5. Finish the Jellyfin setup wizard
6. **Dashboard → API Keys → New** (name it `Home Assistant`) and copy the key

Put media in HA **Media** (`/media`) or **Share** (`/share`) so Jellyfin can see it.

### Docker Compose (non-HA OS hosts)

```bash
docker compose up -d
```

See `docker-compose.yml`.

## Install the Home Assistant integration (HACS)

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

1. Make sure Jellyfin Server is running (add-on or Docker)
2. Create an API key in Jellyfin (**Dashboard → API Keys**)
3. In Home Assistant, add the **Jellyfin** integration
4. Enter:
   - **Server URL** — e.g. `http://127.0.0.1:8096`, `http://homeassistant.local:8096`, or your LAN IP  
     (if you omit the port on `http://`, the integration defaults to **8096**)
   - **API key** — the key you created
   - **Name** (optional) — display name

During setup the integration verifies that the Jellyfin TCP port accepts connections, then checks HTTP reachability and the API key. If you see a connection error, confirm Jellyfin is running and that Home Assistant can reach that host:port.

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

## Development / CI

GitHub Actions runs HACS validation, hassfest, unit tests, and a Docker smoke test that:

1. Starts a mock Jellyfin API on port **8096**
2. Asserts TCP + HTTP connect to port 8096 from the host and from the HA container
3. Boots official Home Assistant in Docker with `jellyfin_ha` installed
4. Loads a pre-seeded config entry against the mock server
5. Fails if setup errors appear or no entities are created

Run the smoke test locally (requires Docker):

```bash
./scripts/ha_docker_smoke.sh
```

## Support

- Issues: [GitHub Issues](https://github.com/chancemcox/Homeassistant-jellyfin/issues)
- Jellyfin docs: https://jellyfin.org/docs/

## License

MIT
