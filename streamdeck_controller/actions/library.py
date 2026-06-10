"""Bibliothek der vorgefertigten Tastenfunktionen.

Jede Aktion hat eine ID, Kategorie, optionale Parameter und Standard-Icons
(normal + aktiv) — wie in Elgatos offizieller Software.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParamSpec:
    key: str
    label: str
    placeholder: str = ""
    kind: str = "text"  # text | int


@dataclass(frozen=True)
class ActionSpec:
    id: str
    name: str
    category: str
    description: str = ""
    toggle: bool = False
    params: tuple = field(default_factory=tuple)
    icon: str = ""         # builtin:<name>
    icon_active: str = ""  # builtin:<name>_active


def _spec(id, name, category, description="", toggle=False, params=(), icon=None):
    icon_name = icon or id
    return ActionSpec(
        id=id, name=name, category=category, description=description,
        toggle=toggle, params=tuple(params),
        icon=f"builtin:{icon_name}",
        icon_active=f"builtin:{icon_name}_active",
    )


ACTION_LIBRARY: list[ActionSpec] = [
    # ── Spotify (Web-API) ─────────────────────────────────────────────
    _spec("spotify_play_pause", "Play / Pause", "Spotify",
          "Wiedergabe starten oder pausieren", toggle=True),
    _spec("spotify_next", "Nächster Song", "Spotify"),
    _spec("spotify_prev", "Vorheriger Song", "Spotify"),
    _spec("spotify_like", "Song liken", "Spotify",
          "Aktuellen Song zu Lieblingssongs hinzufügen/entfernen", toggle=True),
    _spec("spotify_shuffle", "Shuffle", "Spotify",
          "Zufallswiedergabe ein/aus", toggle=True),
    _spec("spotify_vol_up", "Spotify lauter", "Spotify",
          "Spotify-Lautstärke +10%"),
    _spec("spotify_vol_down", "Spotify leiser", "Spotify",
          "Spotify-Lautstärke -10%"),
    _spec("spotify_playlist", "Playlist starten", "Spotify",
          "Playlist/Album per Link oder URI abspielen",
          params=[ParamSpec("uri", "Playlist-Link oder URI", "https://open.spotify.com/playlist/…")]),
    _spec("spotify_device", "Gerät wechseln", "Spotify",
          "Wiedergabe auf anderes Spotify-Gerät schieben",
          params=[ParamSpec("device", "Gerätename (leer = Liste in Benachrichtigung)", "z.B. Arch-PC")]),
    _spec("spotify_now_playing", "Aktueller Song", "Spotify",
          "Zeigt Cover + Titel auf der Taste, Druck = Play/Pause", toggle=True),
    _spec("spotify_song_info", "Song-Info kopieren", "Spotify",
          "Künstler – Titel in die Zwischenablage"),

    # ── System ────────────────────────────────────────────────────────
    _spec("sys_vol_up", "Lautstärke +", "System"),
    _spec("sys_vol_down", "Lautstärke −", "System"),
    _spec("sys_mute", "Stummschalten", "System", toggle=True),
    _spec("sys_mic_mute", "Mikro stumm", "System", toggle=True),
    _spec("sys_brightness_up", "Helligkeit +", "System"),
    _spec("sys_brightness_down", "Helligkeit −", "System"),
    _spec("sys_screenshot", "Screenshot", "System",
          "Bereichs-Screenshot (Spectacle)"),
    _spec("sys_lock", "Bildschirm sperren", "System"),
    _spec("sys_suspend", "Standby", "System", "PC in Bereitschaft versetzen"),
    _spec("sys_poweroff", "Herunterfahren", "System"),
    _spec("sys_reboot", "Neustart", "System"),

    # ── Apps & Web ────────────────────────────────────────────────────
    _spec("app_launch", "App starten", "Apps & Web",
          params=[ParamSpec("cmd", "Programm/Befehl", "z.B. firefox")]),
    _spec("open_url", "URL öffnen", "Apps & Web",
          params=[ParamSpec("url", "URL", "https://…")]),
    _spec("open_folder", "Ordner öffnen", "Apps & Web",
          params=[ParamSpec("path", "Pfad", "~/Downloads")]),

    # ── Seiten ────────────────────────────────────────────────────────
    _spec("page_next", "Nächste Seite", "Seiten"),
    _spec("page_prev", "Vorherige Seite", "Seiten"),
    _spec("page_goto", "Zu Seite springen", "Seiten",
          params=[ParamSpec("page", "Seiten-Nummer (1 = erste)", "1", kind="int")]),

    # ── Sonstige ──────────────────────────────────────────────────────
    _spec("custom_cmd", "Eigener Befehl", "Sonstige",
          "Beliebigen Shell-Befehl ausführen",
          params=[ParamSpec("cmd", "Befehl", "z.B. notify-send Hallo")]),
]

ACTIONS_BY_ID: dict[str, ActionSpec] = {a.id: a for a in ACTION_LIBRARY}

CATEGORIES: list[str] = []
for _a in ACTION_LIBRARY:
    if _a.category not in CATEGORIES:
        CATEGORIES.append(_a.category)


def get_spec(action_id: str) -> ActionSpec | None:
    return ACTIONS_BY_ID.get(action_id)
