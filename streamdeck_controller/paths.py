"""Zentrale Pfade der App."""

import os
from pathlib import Path

APP_NAME = "streamdeck"

PKG_DIR = Path(__file__).resolve().parent
REPO_DIR = PKG_DIR.parent

CONFIG_DIR = Path(os.environ.get("STREAMDECK_CONFIG_DIR", Path.home() / ".config" / APP_NAME)).expanduser()
CONFIG_PATH = CONFIG_DIR / "config.json"
TOKEN_PATH = CONFIG_DIR / "spotify_token.json"
USER_ICONS_DIR = CONFIG_DIR / "icons"

ICONS_DIR = Path(os.environ.get("STREAMDECK_ICONS_DIR", REPO_DIR / "icons")).expanduser()
BUILTIN_ICONS_DIR = ICONS_DIR / "builtin"

LOG_PATH = Path(os.environ.get("STREAMDECK_LOG_PATH", Path.home() / ".streamdeck.log")).expanduser()

_runtime = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/streamdeck-{os.getuid()}"
SOCKET_PATH = Path(os.environ.get("STREAMDECK_SOCKET", Path(_runtime) / "streamdeck.sock"))

FONT_CANDIDATES = [
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",                  # Arch
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",      # Debian/Ubuntu
    "/usr/share/fonts/noto/NotoSans-Bold.ttf",
]


def find_font() -> str | None:
    for cand in FONT_CANDIDATES:
        if Path(cand).exists():
            return cand
    return None


def resolve_icon(ref: str) -> Path | None:
    """Icon-Referenz auflösen: 'builtin:play', absoluter Pfad oder Datei in icons/."""
    if not ref:
        return None
    if ref.startswith("builtin:"):
        p = BUILTIN_ICONS_DIR / f"{ref.split(':', 1)[1]}.png"
        return p if p.exists() else None
    p = Path(os.path.expanduser(ref))
    if p.is_absolute():
        return p if p.exists() else None
    for base in (USER_ICONS_DIR, ICONS_DIR):
        cand = base / ref
        if cand.exists():
            return cand
    return None
