"""Schlanker Spotify-Web-API-Client (nur die Endpunkte, die das Deck braucht)."""

import logging
import re
import time

import requests

from . import auth

log = logging.getLogger(__name__)

API = "https://api.spotify.com/v1"


class SpotifyClient:
    def __init__(self, client_id: str, client_secret: str = ""):
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: dict | None = auth.load_token()

    # ── Token-Handling ───────────────────────────────────────────────
    @property
    def ready(self) -> bool:
        return bool(self.client_id and self._token and self._token.get("refresh_token"))

    def _access_token(self) -> str | None:
        if not self._token:
            self._token = auth.load_token()
        if not self._token:
            return None
        if time.time() > self._token.get("expires_at", 0) - 30:
            self._token = auth.refresh_token(self.client_id, self.client_secret)
        return self._token.get("access_token") if self._token else None

    def _request(self, method: str, path: str, **kwargs):
        token = self._access_token()
        if not token:
            log.warning("Spotify: kein gültiges Token")
            return None
        headers = {"Authorization": f"Bearer {token}"}
        try:
            r = requests.request(method, f"{API}{path}", headers=headers,
                                 timeout=8, **kwargs)
        except requests.RequestException as e:
            log.warning("Spotify-API %s %s: %s", method, path, e)
            return None
        if r.status_code == 401:
            # Token abgelaufen → einmal erneuern und wiederholen
            self._token = auth.refresh_token(self.client_id, self.client_secret)
            token = self._token.get("access_token") if self._token else None
            if not token:
                return None
            headers = {"Authorization": f"Bearer {token}"}
            r = requests.request(method, f"{API}{path}", headers=headers,
                                 timeout=8, **kwargs)
        if r.status_code == 404:
            # kein aktives Gerät
            log.info("Spotify: kein aktives Wiedergabegerät")
            return None
        if r.status_code >= 400:
            log.warning("Spotify-API %s %s: %s %s", method, path, r.status_code, r.text[:200])
            return None
        return r

    # ── Wiedergabe ───────────────────────────────────────────────────
    def playback_state(self) -> dict | None:
        r = self._request("GET", "/me/player")
        if r is None or r.status_code == 204 or not r.text:
            return None
        return r.json()

    def is_playing(self) -> bool:
        state = self.playback_state()
        return bool(state and state.get("is_playing"))

    def play_pause(self):
        state = self.playback_state()
        if state and state.get("is_playing"):
            self._request("PUT", "/me/player/pause")
        else:
            self._request("PUT", "/me/player/play")

    def next_track(self):
        self._request("POST", "/me/player/next")

    def previous_track(self):
        self._request("POST", "/me/player/previous")

    def toggle_shuffle(self) -> bool | None:
        state = self.playback_state()
        if state is None:
            return None
        new = not state.get("shuffle_state", False)
        self._request("PUT", f"/me/player/shuffle?state={'true' if new else 'false'}")
        return new

    def change_volume(self, delta: int):
        state = self.playback_state()
        if not state or not state.get("device"):
            return
        current = state["device"].get("volume_percent", 50)
        new = max(0, min(100, current + delta))
        self._request("PUT", f"/me/player/volume?volume_percent={new}")

    # ── Kontext / Playlists ──────────────────────────────────────────
    @staticmethod
    def to_uri(link_or_uri: str) -> str | None:
        """https://open.spotify.com/playlist/<id> oder spotify:playlist:<id> → URI."""
        s = link_or_uri.strip()
        if s.startswith("spotify:"):
            return s
        m = re.search(r"open\.spotify\.com/(playlist|album|artist|track)/([A-Za-z0-9]+)", s)
        if m:
            return f"spotify:{m.group(1)}:{m.group(2)}"
        return None

    def play_context(self, link_or_uri: str):
        uri = self.to_uri(link_or_uri)
        if not uri:
            log.warning("Spotify: ungültiger Link/URI: %s", link_or_uri)
            return
        if uri.startswith("spotify:track:"):
            self._request("PUT", "/me/player/play", json={"uris": [uri]})
        else:
            self._request("PUT", "/me/player/play", json={"context_uri": uri})

    # ── Geräte ───────────────────────────────────────────────────────
    def list_devices(self) -> list[str]:
        r = self._request("GET", "/me/player/devices")
        if r is None:
            return []
        return [d.get("name", "?") for d in r.json().get("devices", [])]

    def transfer_to_device(self, name: str) -> bool:
        r = self._request("GET", "/me/player/devices")
        if r is None:
            return False
        for d in r.json().get("devices", []):
            if d.get("name", "").lower() == name.lower():
                self._request("PUT", "/me/player",
                              json={"device_ids": [d["id"]], "play": True})
                return True
        return False

    # ── Lieblingssongs ───────────────────────────────────────────────
    def current_track_id(self) -> str | None:
        state = self.playback_state()
        item = (state or {}).get("item") or {}
        return item.get("id")

    def toggle_like_current(self) -> bool | None:
        """Like umschalten. Gibt neuen Zustand zurück (True = geliked)."""
        track_id = self.current_track_id()
        if not track_id:
            return None
        r = self._request("GET", f"/me/tracks/contains?ids={track_id}")
        liked = bool(r is not None and r.json() and r.json()[0])
        if liked:
            self._request("DELETE", f"/me/tracks?ids={track_id}")
            return False
        self._request("PUT", f"/me/tracks?ids={track_id}")
        return True

    def is_current_liked(self) -> bool:
        track_id = self.current_track_id()
        if not track_id:
            return False
        r = self._request("GET", f"/me/tracks/contains?ids={track_id}")
        return bool(r is not None and r.json() and r.json()[0])

    # ── Infos ────────────────────────────────────────────────────────
    def current_song_info(self) -> str | None:
        state = self.playback_state()
        item = (state or {}).get("item")
        if not item:
            return None
        artists = ", ".join(a.get("name", "") for a in item.get("artists", []))
        return f"{artists} – {item.get('name', '')}"

    def now_playing(self) -> dict | None:
        """{'title', 'artist', 'is_playing', 'cover_url'} oder None."""
        state = self.playback_state()
        item = (state or {}).get("item")
        if not item:
            return None
        images = (item.get("album") or {}).get("images") or []
        cover = images[-1].get("url") if images else None  # kleinstes Bild reicht
        return {
            "title": item.get("name", ""),
            "artist": ", ".join(a.get("name", "") for a in item.get("artists", [])),
            "is_playing": bool(state.get("is_playing")),
            "cover_url": cover,
            "track_id": item.get("id"),
        }

    def fetch_cover(self, url: str) -> bytes | None:
        try:
            r = requests.get(url, timeout=8)
            r.raise_for_status()
            return r.content
        except requests.RequestException:
            return None
