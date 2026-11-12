#!/usr/bin/env python3
"""Minimal Jellyfin API mock for Home Assistant smoke tests."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SERVER_ID = "ci-jellyfin-server"
API_KEY = "ci-test-api-key"


class JellyfinHandler(BaseHTTPRequestHandler):
    """Serve the Jellyfin endpoints used by jellyfin_ha."""

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        print(f"[mock-jellyfin] {self.address_string()} - {format % args}")

    def _auth_ok(self) -> bool:
        auth = self.headers.get("Authorization", "")
        token = self.headers.get("X-Emby-Token", "")
        return API_KEY in auth or token == API_KEY

    def _send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_empty(self, status: int = 204) -> None:
        self.send_response(status)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]

        if path == "/System/Info/Public":
            self._send_json(
                {
                    "Id": SERVER_ID,
                    "ServerName": "CI Jellyfin",
                    "Version": "10.10.0",
                }
            )
            return

        if not self._auth_ok():
            self._send_json({"message": "Unauthorized"}, status=401)
            return

        if path == "/System/Info":
            self._send_json(
                {
                    "Id": SERVER_ID,
                    "ServerName": "CI Jellyfin",
                    "Version": "10.10.0",
                    "OperatingSystem": "Linux",
                }
            )
            return

        if path == "/Sessions":
            self._send_json(
                [
                    {
                        "Id": "session-1",
                        "DeviceId": "device-1",
                        "DeviceName": "CI Client",
                        "Client": "Jellyfin Web",
                        "ApplicationVersion": "10.10.0",
                        "UserName": "ci-user",
                        "SupportsMediaControl": True,
                        "SupportedCommands": ["Mute", "Unmute", "SetVolume"],
                        "NowPlayingItem": {
                            "Id": "movie-1",
                            "Name": "Test Movie",
                            "Type": "Movie",
                            "RunTimeTicks": 72_000_000_000,
                            "ImageTags": {"Primary": "abc"},
                        },
                        "PlayState": {
                            "IsPaused": False,
                            "PositionTicks": 600_000_000,
                            "VolumeLevel": 40,
                            "IsMuted": False,
                            "PlayMethod": "DirectPlay",
                        },
                        "LastPlaybackCheckIn": "2024-11-12T18:00:00.0000000Z",
                    }
                ]
            )
            return

        if path == "/Items/Counts":
            self._send_json(
                {
                    "MovieCount": 12,
                    "SeriesCount": 3,
                    "EpisodeCount": 40,
                    "SongCount": 100,
                    "AlbumCount": 20,
                    "ArtistCount": 15,
                }
            )
            return

        if path == "/Users":
            self._send_json([{"Id": "user-1", "Name": "ci-user"}])
            return

        if path == "/Library/VirtualFolders":
            self._send_json(
                [
                    {
                        "Name": "Movies",
                        "CollectionType": "movies",
                        "Locations": ["/data/movies"],
                    }
                ]
            )
            return

        self._send_json({"message": f"Not found: {path}"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if not self._auth_ok():
            self._send_json({"message": "Unauthorized"}, status=401)
            return
        if path == "/Library/Refresh":
            self._send_empty(204)
            return
        if path.startswith("/Sessions/"):
            self._send_empty(204)
            return
        self._send_json({"message": f"Not found: {path}"}, status=404)


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8096), JellyfinHandler)
    print("[mock-jellyfin] listening on 0.0.0.0:8096")
    server.serve_forever()


if __name__ == "__main__":
    main()
