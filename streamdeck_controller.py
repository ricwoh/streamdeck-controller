#!/usr/bin/env python3
"""
Stream Deck Controller
- Single press, long press, double click per key
- Multiple pages with page switching
- Spotify via DBus (play/pause/skip/volume)
- Spotify Web API (playlists, device management)
- Config via ~/.config/streamdeck/config.json
- Tokens cached in ~/.config/streamdeck/spotify_token.json
"""

import json
import os
import sys
import time
import threading
import subprocess
import signal
import logging
import urllib.request
import urllib.parse
import urllib.error
import base64
import http.server
import webbrowser
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import StreamDeck.DeviceManager as DM
from StreamDeck.ImageHelpers import PILHelper
from StreamDeck.Transport.Transport import TransportError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(Path.home() / ".streamdeck.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

CONFIG_PATH = Path.home() / ".config" / "streamdeck" / "config.json"
TOKEN_PATH  = Path.home() / ".config" / "streamdeck" / "spotify_token.json"

DOUBLE_CLICK_INTERVAL = 0.35
LONG_PRESS_THRESHOLD  = 0.6


class SpotifyAPI:
    BASE = "https://api.spotify.com/v1"

    def __init__(self, client_id, client_secret, redirect_uri):
        self.client_id      = client_id
        self.client_secret  = client_secret
        self.redirect_uri   = redirect_uri
        self._token         = None
        self._expires_at    = 0
        self._refresh_token = None
        self._load_token()

    def _load_token(self):
        if TOKEN_PATH.exists():
            try:
                with open(TOKEN_PATH) as f:
                    data = json.load(f)
                self._token         = data.get("access_token")
                self._refresh_token = data.get("refresh_token")
                self._expires_at    = data.get("expires_at", 0)
                log.info("Spotify token loaded from cache.")
            except Exception as e:
                log.warning(f"Could not load token: {e}")

    def _save_token(self):
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_PATH, "w") as f:
            json.dump({
                "access_token":  self._token,
                "refresh_token": self._refresh_token,
                "expires_at":    self._expires_at,
            }, f, indent=2)

    def authenticate(self):
        if self._token and time.time() < self._expires_at - 60:
            log.info("Spotify: using cached token.")
            return
        if self._refresh_token:
            log.info("Spotify: refreshing token.")
            if self._refresh():
                return
        log.info("Spotify: starting OAuth flow.")
        self._oauth_flow()

    def _oauth_flow(self):
        scopes = " ".join([
            "user-read-playback-state",
            "user-modify-playback-state",
            "playlist-read-private",
            "playlist-read-collaborative",
        ])
        params = urllib.parse.urlencode({
            "client_id":     self.client_id,
            "response_type": "code",
            "redirect_uri":  self.redirect_uri,
            "scope":         scopes,
        })
        auth_url = f"https://accounts.spotify.com/authorize?{params}"
        code_holder = {}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                qs = urllib.parse.parse_qs(parsed.query)
                if "code" in qs:
                    code_holder["code"] = qs["code"][0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"<h1>Auth complete. You can close this tab.</h1>")
            def log_message(self, *args):
                pass

        port = int(urllib.parse.urlparse(self.redirect_uri).port or 8888)
        server = http.server.HTTPServer(("localhost", port), Handler)
        log.info(f"Opening browser for Spotify auth.")
        webbrowser.open(auth_url)
        server.handle_request()
        code = code_holder.get("code")
        if not code:
            log.error("Spotify auth failed – no code received.")
            return
        self._exchange_code(code)

    def _exchange_code(self, code):
        data = urllib.parse.urlencode({
            "grant_type":   "authorization_code",
            "code":         code,
            "redirect_uri": self.redirect_uri,
        }).encode()
        self._token_request(data)

    def _refresh(self):
        data = urllib.parse.urlencode({
            "grant_type":    "refresh_token",
            "refresh_token": self._refresh_token,
        }).encode()
        return self._token_request(data)

    def _token_request(self, data):
        creds = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        req = urllib.request.Request(
            "https://accounts.spotify.com/api/token",
            data=data,
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type":  "application/x-www-form-urlencoded",
            }
        )
        try:
            with urllib.request.urlopen(req) as resp:
                body = json.loads(resp.read())
            self._token      = body["access_token"]
            self._expires_at = time.time() + body["expires_in"]
            if "refresh_token" in body:
                self._refresh_token = body["refresh_token"]
            self._save_token()
            log.info("Spotify token obtained.")
            return True
        except Exception as e:
            log.error(f"Spotify token request failed: {e}")
            return False

    def _ensure_token(self):
        if not self._token or time.time() >= self._expires_at - 60:
            if self._refresh_token:
                self._refresh()
            else:
                log.error("No Spotify token.")

    def _request(self, method, path, body=None):
        self._ensure_token()
        url  = f"{self.BASE}{path}"
        data = json.dumps(body).encode() if body else None
        req  = urllib.request.Request(
            url, data=data, method=method,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type":  "application/json",
            }
        )
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            log.error(f"Spotify API {method} {path} -> {e.code}: {e.read()}")
            return None
        except Exception as e:
            log.error(f"Spotify API error: {e}")
            return None

    def get_playback(self):
        return self._request("GET", "/me/player")

    def set_volume(self, percent):
        percent = max(0, min(100, int(percent)))
        self._request("PUT", f"/me/player/volume?volume_percent={percent}")

    def get_devices(self):
        resp = self._request("GET", "/me/player/devices")
        return resp.get("devices", []) if resp else []

    def get_playlists(self):
        resp = self._request("GET", "/me/playlists?limit=50")
        return resp.get("items", []) if resp else []

    def play_playlist(self, playlist_uri, device_id=None):
        path = "/me/player/play"
        if device_id:
            path += f"?device_id={device_id}"
        self._request("PUT", path, {"context_uri": playlist_uri})

    def transfer_playback(self, device_id):
        self._request("PUT", "/me/player", {"device_ids": [device_id], "play": True})

    def set_shuffle(self, state):
        self._request("PUT", f"/me/player/shuffle?state={'true' if state else 'false'}")

    def set_repeat(self, mode):
        self._request("PUT", f"/me/player/repeat?state={mode}")


def spotify_dbus(action):
    base = ["dbus-send", "--print-reply", "--dest=org.mpris.MediaPlayer2.spotify",
            "/org/mpris/MediaPlayer2"]
    try:
        if action == "play_pause":
            subprocess.run(base + ["org.mpris.MediaPlayer2.Player.PlayPause"], check=True)
        elif action == "next":
            subprocess.run(base + ["org.mpris.MediaPlayer2.Player.Next"], check=True)
        elif action == "previous":
            subprocess.run(base + ["org.mpris.MediaPlayer2.Player.Previous"], check=True)
        elif action == "stop":
            subprocess.run(base + ["org.mpris.MediaPlayer2.Player.Stop"], check=True)
        elif action == "volume_up":
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"], check=True)
        elif action == "volume_down":
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%"], check=True)
        elif action == "open_spotify":
            subprocess.Popen(["spotify"])
    except Exception as e:
        log.warning(f"DBus '{action}' failed: {e}")


def claude_api_action(mode, config, controller=None, key=None, page=None):
    import urllib.request, urllib.error, json, base64, tempfile, os

    api_key = config.get("claude_api", {}).get("api_key", "")

    def set_active(state):
        if controller is not None and key is not None and page is not None:
            controller.toggle_state[(page, key)] = state
            controller.render_key(page, key)

    def show_result(text):
        proc = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
        proc.communicate(text.encode())
        subprocess.Popen(["python3",
                          "/home/rico/Programmieren/Projekte/diktieren/result-overlay.py",
                          text])

    if not api_key:
        show_result("Claude API Key fehlt in config.json")
        return

    def ask_claude(messages):
        payload = json.dumps({
            "model": "claude-opus-4-6",
            "max_tokens": 1024,
            "messages": messages
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return data["content"][0]["text"]

    try:
        if mode == "clipboard":
            result = subprocess.run(["xclip", "-selection", "clipboard", "-o"],
                                    capture_output=True, text=True, timeout=3)
            text = result.stdout.strip()
            if not text:
                show_result("Clipboard ist leer.")
                return
            set_active(True)
            answer = ask_claude([{"role": "user", "content": text}])
            set_active(False)
            show_result(answer)

        elif mode == "screenshot":
            dlg = subprocess.run(
                ["zenity", "--entry", "--title=Claude", "--text=Frage zum Screenshot:"],
                capture_output=True, text=True
            )
            question = dlg.stdout.strip()
            if not question:
                return
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.close()
            subprocess.run(["gnome-screenshot", "-f", tmp.name], check=True)
            with open(tmp.name, "rb") as f:
                img_b64 = base64.standard_b64encode(f.read()).decode()
            os.unlink(tmp.name)
            set_active(True)
            messages = [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                {"type": "text", "text": question}
            ]}]
            answer = ask_claude(messages)
            set_active(False)
            show_result(answer)

        elif mode == "ask":
            dlg = subprocess.run(
                ["zenity", "--entry", "--title=Claude", "--text=Frage an Claude:", "--width=400"],
                capture_output=True, text=True
            )
            question = dlg.stdout.strip()
            if not question:
                return
            set_active(True)
            answer = ask_claude([{"role": "user", "content": question}])
            set_active(False)
            show_result(answer)

    except Exception as e:
        set_active(False)
        show_result(f"Fehler: {e}")


def run_action(action, controller):
    t = action.get("type")

    if t == "spotify_dbus":
        spotify_dbus(action.get("command"))

    elif t == "spotify_playlist":
        if controller.spotify:
            controller.spotify.play_playlist(
                action.get("uri"), action.get("device_id"))
        else:
            log.warning("Spotify API not configured.")

    elif t == "spotify_device":
        if controller.spotify:
            controller.spotify.transfer_playback(action.get("device_id"))
        else:
            log.warning("Spotify API not configured.")

    elif t == "spotify_shuffle":
        if controller.spotify:
            controller.spotify.set_shuffle(action.get("state", True))

    elif t == "spotify_repeat":
        if controller.spotify:
            controller.spotify.set_repeat(action.get("mode", "context"))

    elif t == "toggle":
        key  = action.get("_key")
        page = action.get("_page")
        if key is not None and page is not None:
            state = controller.toggle_state.get((page, key), False)
            controller.toggle_state[(page, key)] = not state
            controller.render_key(page, key)
        then = action.get("then")
        if then:
            run_action(dict(then, _key=action.get("_key"), _page=action.get("_page")), controller)

    elif t == "spotify_volume":
        if controller.spotify:
            cmd      = action.get("command")
            playback = controller.spotify.get_playback()
            if playback and "device" in playback:
                current = playback["device"].get("volume_percent", 50)
                if cmd == "set_volume":
                    controller.spotify.set_volume(action.get("value", 50))
                else:
                    delta = action.get("delta", 10)
                    controller.spotify.set_volume(current + (delta if cmd == "volume_up" else -delta))
            else:
                log.warning("Spotify: no active device for volume control.")
        else:
            log.warning("Spotify API not configured for volume control.")

    elif t == "song_info_clipboard":
        try:
            import re
            result = subprocess.run(
                ["dbus-send", "--print-reply", "--dest=org.mpris.MediaPlayer2.spotify",
                 "/org/mpris/MediaPlayer2",
                 "org.freedesktop.DBus.Properties.Get",
                 "string:org.mpris.MediaPlayer2.Player",
                 "string:Metadata"],
                capture_output=True, text=True, timeout=3
            )
            out      = result.stdout
            title_m  = re.search(r'"xesam:title".*?\n\s+variant\s+string\s+"([^"]+)"', out)
            artist_m = re.search(r'"xesam:artist".*?\n.*?\n\s+"([^"]+)"', out)
            title  = title_m.group(1)  if title_m  else ""
            artist = artist_m.group(1) if artist_m else ""
            text   = f"{artist} – {title}" if artist and title else title or "Kein Song"
            proc   = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
            proc.communicate(text.encode())
            log.info(f"Song info copied: {text}")
        except Exception as e:
            log.error(f"song_info_clipboard: {e}")

    elif t == "command":
        cmd = action.get("cmd")
        if cmd:
            subprocess.Popen(cmd, shell=True)

    elif t == "page":
        controller.switch_page(action.get("target", 0))

    elif t == "key":
        subprocess.Popen(["xdotool", "key", action.get("keys", "")])

    elif t == "text":
        subprocess.Popen(["xdotool", "type", "--", action.get("text", "")])

    elif t == "claude_api":
        mode = action.get("mode", "clipboard")
        cfg  = getattr(controller, 'config', {})
        key  = action.get("_key")
        page = action.get("_page")
        threading.Thread(target=claude_api_action, args=(mode, cfg, controller, key, page), daemon=True).start()

    else:
        log.warning(f"Unknown action type: {t}")


def render_key_image(deck, label, icon_path=None,
                     bg_color=(30,30,30), text_color=(255,255,255)):
    # PILHelper creates an image in the correct orientation for this device
    img = PILHelper.create_key_image(deck, background=bg_color)
    w, h = img.size

    if icon_path:
        icon_path = os.path.expanduser(icon_path)
    if icon_path and os.path.exists(icon_path):
        try:
            icon = Image.open(icon_path).convert("RGBA").resize((w, h))
            img.paste(icon, (0, 0), icon)
        except Exception as e:
            log.warning(f"Icon load failed {icon_path}: {e}")

    if label:
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
        except Exception:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), label, font=font)
        tw   = bbox[2] - bbox[0]
        tx   = (w - tw) // 2
        ty   = h - 18
        draw.text((tx + 1, ty + 1), label, fill=(0, 0, 0), font=font)
        draw.text((tx,     ty),     label, fill=text_color,  font=font)

    return PILHelper.to_native_key_format(deck, img)


class StreamDeckController:
    def __init__(self, config):
        self.config       = config
        self.current_page = 0
        self.pages        = config.get("pages", [{}])
        self._press_time  = {}
        self._press_count = {}
        self._press_timer = {}
        self._lock        = threading.Lock()
        self.deck         = None
        self.toggle_state = {}  # (page_index, key) -> bool

        sp_cfg = config.get("spotify_api")
        if sp_cfg and sp_cfg.get("client_id") not in (None, "", "YOUR_CLIENT_ID"):
            self.spotify = SpotifyAPI(
                sp_cfg["client_id"],
                sp_cfg["client_secret"],
                sp_cfg.get("redirect_uri", "http://localhost:8888/callback"),
            )
            threading.Thread(target=self.spotify.authenticate, daemon=True).start()
        else:
            self.spotify = None
            log.info("Spotify Web API not configured – DBus-only mode.")

    def start(self):
        devices = DM.DeviceManager().enumerate()
        if not devices:
            log.error("No Stream Deck found.")
            sys.exit(1)

        self.deck = devices[0]
        self.deck.open()
        self.deck.reset()
        self.deck.set_brightness(self.config.get("brightness", 80))
        self.deck.set_key_callback(self._key_callback)
        log.info(f"Connected: {self.deck.deck_type()} | Keys: {self.deck.key_count()}")
        self.render_page()
        threading.Thread(target=self._spotify_status_poller, daemon=True).start()

        try:
            signal.pause()
        except KeyboardInterrupt:
            pass
        finally:
            self.deck.reset()
            self.deck.close()

    def switch_page(self, page_index):
        if 0 <= page_index < len(self.pages):
            self.current_page = page_index
            self.render_page()
            log.info(f"Switched to page {page_index}")

    def render_page(self):
        for i in range(self.deck.key_count()):
            self.render_key(self.current_page, i)

    def render_key(self, page_index, key):
        if page_index != self.current_page:
            return
        page     = self.pages[page_index]
        key_conf = page.get("keys", {}).get(str(key), {})
        active   = self.toggle_state.get((page_index, key), False)
        if active and "icon_active" in key_conf:
            icon = key_conf["icon_active"]
        else:
            icon = key_conf.get("icon")
        if active and "label_active" in key_conf:
            label = key_conf["label_active"]
        else:
            label = key_conf.get("label", "")
        bg = tuple(key_conf.get("bg_color",   [30, 30, 30]))
        fg = tuple(key_conf.get("text_color", [255, 255, 255]))
        self.deck.set_key_image(key, render_key_image(self.deck, label, icon, bg, fg))

    def _spotify_status_poller(self):
        """Poll Spotify playback state via DBus and update keys that use spotify_status_icon."""
        last_state = None
        while True:
            try:
                result = subprocess.run(
                    ["dbus-send", "--print-reply", "--dest=org.mpris.MediaPlayer2.spotify",
                     "/org/mpris/MediaPlayer2",
                     "org.freedesktop.DBus.Properties.Get",
                     "string:org.mpris.MediaPlayer2.Player",
                     "string:PlaybackStatus"],
                    capture_output=True, text=True, timeout=2
                )
                playing = "Playing" in result.stdout
                if playing != last_state:
                    last_state = playing
                    self._update_spotify_icons(playing)
            except Exception:
                pass
            time.sleep(2)

    def _update_spotify_icons(self, playing):
        """Update all keys that have spotify_status_icon=true based on playback state."""
        for pi, page in enumerate(self.pages):
            for k, key_conf in page.get("keys", {}).items():
                if key_conf.get("spotify_status_icon"):
                    self.toggle_state[(pi, int(k))] = not playing
                    self.render_key(pi, int(k))

    def _key_callback(self, deck, key, pressed):
        if pressed:
            self._on_press(key)
        else:
            self._on_release(key)

    def _on_press(self, key):
        with self._lock:
            self._press_time[key] = time.time()
            if key in self._press_timer and self._press_timer[key]:
                self._press_timer[key].cancel()

    def _on_release(self, key):
        with self._lock:
            press_time = self._press_time.pop(key, None)
            if press_time is None:
                return
            duration = time.time() - press_time

        if duration >= LONG_PRESS_THRESHOLD:
            self._fire(key, "long_press")
            with self._lock:
                self._press_count[key] = 0
            return

        with self._lock:
            self._press_count[key] = self._press_count.get(key, 0) + 1
            if key in self._press_timer and self._press_timer[key]:
                self._press_timer[key].cancel()

        def decide():
            with self._lock:
                n = self._press_count.pop(key, 0)
            if n >= 2:
                self._fire(key, "double_click")
            else:
                self._fire(key, "single_press")

        t = threading.Timer(DOUBLE_CLICK_INTERVAL, decide)
        with self._lock:
            self._press_timer[key] = t
        t.start()

    def _fire(self, key, event_type):
        page     = self.pages[self.current_page]
        key_conf = page.get("keys", {}).get(str(key), {})
        action   = key_conf.get(event_type)
        if not action:
            log.debug(f"Key {key} -> {event_type} -> no action")
            return
        # inject key/page context for toggle action
        if isinstance(action, dict):
            action = dict(action, _key=key, _page=self.current_page)
        if isinstance(action, list):
            log.info(f"Key {key} -> {event_type} -> {len(action)} actions")
            cur_key  = key
            cur_page = self.current_page
            def run_sequence():
                for a in action:
                    delay = a.pop("delay", 0)
                    if delay:
                        time.sleep(delay)
                    run_action(dict(a, _key=cur_key, _page=cur_page), self)
                    a["delay"] = delay  # restore for next press
            threading.Thread(target=run_sequence, daemon=True).start()
        else:
            log.info(f"Key {key} -> {event_type} -> {action}")
            threading.Thread(
                target=run_action, args=(action, self), daemon=True
            ).start()


DEFAULT_CONFIG = {
    "brightness": 80,
    "spotify_api": {
        "client_id":     "YOUR_CLIENT_ID",
        "client_secret": "YOUR_CLIENT_SECRET",
        "redirect_uri":  "http://localhost:8888/callback"
    },
    "pages": [
        {
            "name": "Main",
            "keys": {
                "0": {"label": "Play/Pause", "single_press": {"type": "spotify_dbus", "command": "play_pause"}},
                "1": {"label": "<<",         "single_press": {"type": "spotify_dbus", "command": "previous"}},
                "2": {"label": ">>",         "single_press": {"type": "spotify_dbus", "command": "next"}},
                "3": {"label": "Vol +", "single_press": {"type": "spotify_dbus", "command": "volume_up"},   "long_press": {"type": "spotify_dbus", "command": "volume_up"}},
                "4": {"label": "Vol -", "single_press": {"type": "spotify_dbus", "command": "volume_down"}, "long_press": {"type": "spotify_dbus", "command": "volume_down"}},
                "5": {"label": "v Listen",  "single_press": {"type": "page", "target": 1}}
            }
        },
        {
            "name": "Playlists",
            "keys": {
                "0": {"label": "Playlist 1", "single_press": {"type": "spotify_playlist", "uri": "spotify:playlist:DEINE_PLAYLIST_URI"}},
                "1": {"label": "Playlist 2", "single_press": {"type": "spotify_playlist", "uri": "spotify:playlist:DEINE_PLAYLIST_URI"}},
                "3": {"label": "v Geraete",  "single_press": {"type": "page", "target": 2}},
                "5": {"label": "^ Main",     "single_press": {"type": "page", "target": 0}}
            }
        },
        {
            "name": "Devices",
            "keys": {
                "0": {"label": "PC",    "single_press": {"type": "spotify_device", "device_id": "DEINE_DEVICE_ID"}},
                "1": {"label": "Phone", "single_press": {"type": "spotify_device", "device_id": "DEINE_DEVICE_ID"}},
                "5": {"label": "^ Main","single_press": {"type": "page", "target": 0}}
            }
        }
    ]
}


def list_spotify_info(config):
    sp_cfg = config.get("spotify_api", {})
    if sp_cfg.get("client_id") in (None, "", "YOUR_CLIENT_ID"):
        print("Spotify API nicht konfiguriert.")
        return
    api = SpotifyAPI(
        sp_cfg["client_id"],
        sp_cfg["client_secret"],
        sp_cfg.get("redirect_uri", "http://localhost:8888/callback")
    )
    api.authenticate()

    print("\n── Geraete ──────────────────────────────────────")
    for d in api.get_devices():
        active = " (aktiv)" if d.get("is_active") else ""
        print(f"  {d['name']}{active}")
        print(f"    ID:   {d['id']}")
        print(f"    Type: {d['type']}")

    print("\n── Playlists ─────────────────────────────────────")
    for p in api.get_playlists():
        if p:
            print(f"  {p['name']}")
            print(f"    URI: {p['uri']}")


def main():
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not CONFIG_PATH.exists():
        with open(CONFIG_PATH, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        log.info(f"Default config created at {CONFIG_PATH}")

    with open(CONFIG_PATH) as f:
        config = json.load(f)

    if len(sys.argv) > 1 and sys.argv[1] == "--list-devices":
        list_spotify_info(config)
        return

    controller = StreamDeckController(config)
    controller.start()


if __name__ == "__main__":
    main()
