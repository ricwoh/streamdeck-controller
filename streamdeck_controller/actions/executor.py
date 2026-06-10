"""Ausführung der Tastenfunktionen.

Der Executor bekommt einen Kontext (Daemon) mit Spotify-Client und
Seitensteuerung und führt Aktionen anhand ihrer ID aus.
"""

import logging
import shutil
import subprocess

log = logging.getLogger(__name__)


def _run(cmd: str | list, shell: bool | None = None):
    """Befehl ohne Blockieren starten."""
    if isinstance(cmd, str):
        subprocess.Popen(cmd, shell=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(cmd,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def notify(title: str, message: str = "", icon: str = "dialog-information"):
    if shutil.which("notify-send"):
        _run(["notify-send", "--app-name=Stream Deck", f"--icon={icon}", title, message])


def copy_clipboard(text: str):
    """Wayland zuerst (wl-copy), X11-Fallback (xclip)."""
    if shutil.which("wl-copy"):
        p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
    elif shutil.which("xclip"):
        p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
    else:
        notify("Zwischenablage", "wl-clipboard oder xclip installieren", "dialog-error")
        return
    p.communicate(text.encode(), timeout=3)


def _volume_cmd(direction: str) -> str:
    """PipeWire (wpctl) bevorzugen, sonst PulseAudio (pactl)."""
    if shutil.which("wpctl"):
        return {
            "up": "wpctl set-volume -l 1.5 @DEFAULT_AUDIO_SINK@ 5%+",
            "down": "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-",
            "mute": "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle",
            "mic_mute": "wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle",
        }[direction]
    return {
        "up": "pactl set-sink-volume @DEFAULT_SINK@ +5%",
        "down": "pactl set-sink-volume @DEFAULT_SINK@ -5%",
        "mute": "pactl set-sink-mute @DEFAULT_SINK@ toggle",
        "mic_mute": "pactl set-source-mute @DEFAULT_SOURCE@ toggle",
    }[direction]


def _screenshot_cmd() -> str:
    if shutil.which("spectacle"):
        return "spectacle -r"  # KDE: Bereich auswählen
    if shutil.which("flameshot"):
        return "flameshot gui"
    return "spectacle -r"


class ActionExecutor:
    """Führt Aktionen aus. ctx muss bieten:
    - ctx.spotify  -> SpotifyClient oder None
    - ctx.goto_page(idx) / ctx.next_page() / ctx.prev_page()
    """

    def __init__(self, ctx):
        self.ctx = ctx

    def execute(self, action: dict):
        if not action:
            return
        action_id = action.get("id", "")
        params = action.get("params", {})
        handler = getattr(self, f"_do_{action_id}", None)
        if handler is None:
            log.warning("Unbekannte Aktion: %s", action_id)
            return
        try:
            handler(params)
        except Exception as e:
            log.error("Aktion %s fehlgeschlagen: %s", action_id, e)
            notify("Stream Deck", f"Aktion fehlgeschlagen: {e}", "dialog-error")

    # ── Spotify (Web-API) ─────────────────────────────────────────────
    def _spotify(self):
        sp = getattr(self.ctx, "spotify", None)
        if sp is None or not sp.ready:
            notify("Spotify nicht verbunden",
                   "Im Terminal anmelden: streamdeck spotify login", "dialog-warning")
            return None
        return sp

    def _do_spotify_play_pause(self, params):
        if sp := self._spotify():
            sp.play_pause()

    def _do_spotify_next(self, params):
        if sp := self._spotify():
            sp.next_track()

    def _do_spotify_prev(self, params):
        if sp := self._spotify():
            sp.previous_track()

    def _do_spotify_like(self, params):
        if sp := self._spotify():
            liked = sp.toggle_like_current()
            if liked is not None:
                notify("Spotify", "❤ Zu Lieblingssongs hinzugefügt" if liked
                       else "Aus Lieblingssongs entfernt")

    def _do_spotify_shuffle(self, params):
        if sp := self._spotify():
            sp.toggle_shuffle()

    def _do_spotify_vol_up(self, params):
        if sp := self._spotify():
            sp.change_volume(+10)

    def _do_spotify_vol_down(self, params):
        if sp := self._spotify():
            sp.change_volume(-10)

    def _do_spotify_playlist(self, params):
        if sp := self._spotify():
            uri = params.get("uri", "").strip()
            if uri:
                sp.play_context(uri)
            else:
                notify("Spotify", "Keine Playlist eingestellt", "dialog-warning")

    def _do_spotify_device(self, params):
        if sp := self._spotify():
            name = params.get("device", "").strip()
            if name:
                if not sp.transfer_to_device(name):
                    notify("Spotify", f"Gerät '{name}' nicht gefunden", "dialog-warning")
            else:
                devices = sp.list_devices()
                notify("Spotify-Geräte", "\n".join(devices) or "Keine Geräte aktiv")

    def _do_spotify_now_playing(self, params):
        if sp := self._spotify():
            sp.play_pause()

    def _do_spotify_song_info(self, params):
        if sp := self._spotify():
            info = sp.current_song_info()
            if info:
                copy_clipboard(info)
                notify("Kopiert", info)
            else:
                notify("Spotify", "Gerade läuft nichts")

    # ── System ────────────────────────────────────────────────────────
    def _do_sys_vol_up(self, params):
        _run(_volume_cmd("up"))

    def _do_sys_vol_down(self, params):
        _run(_volume_cmd("down"))

    def _do_sys_mute(self, params):
        _run(_volume_cmd("mute"))

    def _do_sys_mic_mute(self, params):
        _run(_volume_cmd("mic_mute"))

    def _do_sys_brightness_up(self, params):
        _run("brightnessctl set +10%")

    def _do_sys_brightness_down(self, params):
        _run("brightnessctl set 10%-")

    def _do_sys_screenshot(self, params):
        _run(_screenshot_cmd())

    def _do_sys_lock(self, params):
        _run("loginctl lock-session")

    def _do_sys_suspend(self, params):
        _run("systemctl suspend")

    def _do_sys_poweroff(self, params):
        _run("systemctl poweroff")

    def _do_sys_reboot(self, params):
        _run("systemctl reboot")

    # ── Apps & Web ────────────────────────────────────────────────────
    def _do_app_launch(self, params):
        cmd = params.get("cmd", "").strip()
        if cmd:
            _run(cmd)

    def _do_open_url(self, params):
        url = params.get("url", "").strip()
        if url:
            _run(["xdg-open", url])

    def _do_open_folder(self, params):
        import os
        path = os.path.expanduser(params.get("path", "").strip() or "~")
        _run(["xdg-open", path])

    # ── Seiten ────────────────────────────────────────────────────────
    def _do_page_next(self, params):
        self.ctx.next_page()

    def _do_page_prev(self, params):
        self.ctx.prev_page()

    def _do_page_goto(self, params):
        try:
            page = int(params.get("page", 1)) - 1
        except (TypeError, ValueError):
            page = 0
        self.ctx.goto_page(max(0, page))

    # ── Sonstige ──────────────────────────────────────────────────────
    def _do_custom_cmd(self, params):
        cmd = params.get("cmd", "").strip()
        if cmd:
            _run(cmd)
