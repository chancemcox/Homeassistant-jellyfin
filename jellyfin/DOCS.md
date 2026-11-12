# Jellyfin Server add-on

Runs the official Jellyfin media server on Home Assistant OS and exposes it on port **8096**.

## Install

1. In Home Assistant go to **Settings → Add-ons → Add-on store**
2. ⋮ menu → **Repositories**
3. Add: `https://github.com/chancemcox/Homeassistant-jellyfin`
4. Find **Jellyfin Server** → **Install**
5. Start the add-on
6. Open the **Web UI** (or visit `http://homeassistant.local:8096`)

## First-run setup

1. Complete the Jellyfin wizard
2. Add your media libraries (files under `/media` or `/share` are available)
3. Go to **Dashboard → API Keys → New**
4. Name it `Home Assistant` and copy the key

## Connect Home Assistant

1. Install the **Jellyfin** integration via HACS from this same repository (if not already installed)
2. Restart Home Assistant
3. **Settings → Devices & services → Add integration → Jellyfin**
4. URL: `http://127.0.0.1:8096` or `http://homeassistant.local:8096` or your LAN IP
5. Paste the API key

## Ports

| Port | Purpose |
| --- | --- |
| 8096 | Web UI + API (published by default) |
| 8920 | Optional HTTPS (disabled by default) |

## Notes

- Data is stored in the add-on persistent `/data` directory
- Put media in Home Assistant **Media** (`/media`) or **Share** (`/share`)
- Twingate users: allow TCP **8096** to your HA host in the Twingate Resource
