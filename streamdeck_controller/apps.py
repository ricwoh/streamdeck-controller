"""Installierte Desktop-Anwendungen (.desktop-Dateien) auflisten.

Für die „App starten“-Auswahl in der GUI: liefert (Name, Befehl)-Paare aller
sichtbaren Anwendungen aus den XDG-Datenverzeichnissen. Der Befehl ist die
Exec-Zeile ohne Feldcodes (%u, %F, …) und kann direkt über die Shell
gestartet werden.
"""

import os
import re
from pathlib import Path

_FIELD_CODE = re.compile(r"\s*%[fFuUdDnNickvm]")


def _data_dirs() -> list[Path]:
    home = Path(os.environ.get("XDG_DATA_HOME") or "~/.local/share").expanduser()
    dirs = [home]
    for entry in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":"):
        if entry:
            dirs.append(Path(entry).expanduser())
    return dirs


def strip_field_codes(exec_line: str) -> str:
    """Feldcodes wie %u/%F aus einer Exec-Zeile entfernen."""
    return _FIELD_CODE.sub("", exec_line).strip()


def parse_desktop_file(path: Path) -> tuple[str, str] | None:
    """(Name, Befehl) einer .desktop-Datei — None für versteckte Einträge."""
    entry: dict[str, str] = {}
    in_entry = False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            if in_entry:
                break  # nur die [Desktop Entry]-Sektion interessiert
            in_entry = line == "[Desktop Entry]"
            continue
        if not in_entry or not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        entry.setdefault(key.strip(), value.strip())

    name, exec_line = entry.get("Name", ""), entry.get("Exec", "")
    if not name or not exec_line:
        return None
    if entry.get("Type") != "Application":  # Pflichtfeld laut Spezifikation
        return None
    if "true" in (entry.get("NoDisplay", "").lower(), entry.get("Hidden", "").lower(),
                  entry.get("Terminal", "").lower()):
        return None
    return name, strip_field_codes(exec_line)


def list_desktop_apps() -> list[tuple[str, str]]:
    """Alle sichtbaren installierten Apps, alphabetisch nach Name.

    Bei gleicher Datei-ID gewinnt das zuerst durchsuchte Verzeichnis
    (XDG_DATA_HOME vor den System-Verzeichnissen).
    """
    seen: dict[str, tuple[str, str]] = {}
    for base in _data_dirs():
        app_dir = base / "applications"
        if not app_dir.is_dir():
            continue
        for path in app_dir.rglob("*.desktop"):
            file_id = str(path.relative_to(app_dir))
            if file_id in seen:
                continue
            parsed = parse_desktop_file(path)
            if parsed:
                seen[file_id] = parsed
    return sorted(set(seen.values()), key=lambda item: item[0].lower())
