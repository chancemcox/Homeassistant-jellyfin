#!/bin/bash
set -euo pipefail

mkdir -p /data/config /data/log /data/cache

echo "[jellyfin] Starting Jellyfin Server..."
echo "[jellyfin] Web UI / API will be on port 8096"
echo "[jellyfin] Media is available under /media and /share"
echo "[jellyfin] After setup: Dashboard → API Keys → create a key for Home Assistant"

# Prefer the binary shipped by the official image.
if [[ -x /jellyfin/jellyfin ]]; then
  exec /jellyfin/jellyfin \
    --datadir /data \
    --configdir /data/config \
    --logdir /data/log \
    --cachedir /data/cache
fi

# Fallback for image layout changes.
exec jellyfin \
  --datadir /data \
  --configdir /data/config \
  --logdir /data/log \
  --cachedir /data/cache
