# streamdeck-controller

GUI-Konfigurator und Controller für Elgato Stream Decks auf Linux (Arch/KDE im Fokus).

## Features

- **Geräteerkennung:** alle angeschlossenen Stream Decks werden gefunden, Auswahl in der GUI
- **Drag & Drop:** vorgefertigte Funktionen aus der Palette auf Tasten ziehen (wie in Elgatos App)
- **Tastengrafiken:** jede Funktion bringt eine normale und eine aktive Grafik mit; eigene Icons möglich
- **Multi-Press:** pro Taste drei Belegungen — 1× drücken, 2× drücken, gedrückt halten
- **Spotify über Web-API:** Play/Pause, Skip, Liken, Shuffle, Playlists, Gerätewechsel, Cover auf der Taste
- **System-Aktionen:** Lautstärke, Mikro, Helligkeit, Screenshot, Sperren, Standby, Herunterfahren, Neustart
- **Apps & Web:** Programme starten, URLs und Ordner öffnen, eigene Befehle
- **Seiten:** mehrere Tastenebenen mit Umschalt-Tasten
- **Daemon + GUI getrennt:** der Hintergrunddienst läuft ohne Fenster, die GUI konfiguriert live
- **Autostart:** systemd-User-Service, startet zuverlässig mit der Anmeldung
- **CLI:** `streamdeck` zeigt alle Befehle (run, start, stop, restart, status, ui, devices, log, …)

## Installation (Arch Linux)

```bash
git clone https://github.com/ricwoh/streamdeck-controller.git
cd streamdeck-controller
./install.sh
```

Der Installer richtet venv, udev-Regel, `streamdeck`-Befehl, App-Menü-Eintrag und Autostart ein.

Danach:

```bash
streamdeck ui        # GUI öffnen und Tasten belegen
streamdeck           # alle Befehle anzeigen
streamdeck status    # läuft alles?
```

## Spotify einrichten (einmalig)

Die Spotify-Steuerung läuft komplett über die Web-API (Spotify Premium nötig):

1. <https://developer.spotify.com/dashboard> → „Create app“
   - Redirect URI: `http://127.0.0.1:8888/callback`
   - API: Web API
2. Client-ID kopieren
3. In der GUI auf **Spotify…** klicken, Client-ID einfügen, **Anmelden** —
   oder im Terminal: `streamdeck spotify login`

## Multi-Press

In der GUI hat jede Taste drei Tabs: **Drücken**, **2× Drücken**, **Halten**.
Ist nur „Drücken“ belegt, löst die Taste ohne Verzögerung aus.
Zeitfenster sind in `~/.config/streamdeck/config.json` unter `timing` einstellbar.

## CLI

```text
streamdeck run|start|stop|restart|status   Daemon steuern
streamdeck ui                              GUI öffnen
streamdeck devices                         Decks auflisten
streamdeck log                             Log live verfolgen
streamdeck spotify login|status|logout     Spotify-Anbindung
streamdeck autostart on|off|status         Autostart (systemd --user)
```

## Aus Source starten (Entwicklung)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
./streamdeck devices
./streamdeck run        # Daemon im Vordergrund
./streamdeck ui         # GUI
python -m pytest -q     # Tests
```

Mitgelieferte Tastengrafiken neu erzeugen: `python tools/generate_icons.py`

## Projekt-Checks

```bash
./tools/release-check.sh      # Git-Status, Secrets, Syntax, Tests, Packaging
./tools/update-aur.sh         # AUR-Arbeitskopie aus Vorlage synchronisieren
./tools/test-arch-package.sh  # echter makepkg/namcap-Lauf (Arch oder Docker)
```

## Arch Linux / AUR

Statische AUR-Vorlage unter `aur/`. Finale Prüfung auf Arch:

```bash
cd aur/aur-repo
makepkg --printsrcinfo > .SRCINFO
makepkg -sf
namcap PKGBUILD && namcap *.pkg.tar.*
```

## Wichtige Dateien

- `streamdeck_controller/` — Python-Paket (Daemon, GUI, Aktionen, Spotify, CLI)
- `streamdeck` — CLI-Wrapper für Source-Checkouts
- `install.sh` — lokale Installation
- `data/` — udev-Regel und Desktop-Eintrag
- `icons/builtin/` — generierte Standard-Tastengrafiken
- `aur/PKGBUILD` — AUR-Packaging

## Konfiguration

`~/.config/streamdeck/config.json` — wird von der GUI gepflegt; eine alte
v1-Konfiguration (`streamdeck_app.py`) wird beim ersten Start automatisch
migriert (Backup: `config.json.v1-backup`).

## Lizenz

MIT — siehe `LICENSE`.
