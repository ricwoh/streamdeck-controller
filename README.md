# streamdeck-controller

GUI-Konfigurator und Controller für Elgato Stream Deck auf Linux.

## Features

- PySide6-GUI zum Belegen der Stream-Deck-Tasten
- Seiten, Icons, Labels und vordefinierte Aktionen
- Spotify/MPRIS-, System- und Custom-Command-Aktionen
- udev-Regel für Zugriff ohne root
- AUR/PKGBUILD-Vorbereitung für Arch/yay

## Aus Source starten

```bash
git clone https://github.com/ricwoh/streamdeck-controller.git
cd streamdeck-controller
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 streamdeck_app.py
```

Geräte prüfen:

```bash
python3 streamdeck_app.py --list-devices
```

## Lokale Installation

```bash
./install.sh
streamdeck-controller
```

Der Installer legt einen venv unter `~/.venv/streamdeck`, einen Starter unter `~/.local/bin/streamdeck-controller` und einen Desktop-Eintrag an.

## Arch Linux / AUR

Im Repo liegt die statische AUR-Vorlage unter `aur/`. Finale Arch-Prüfung muss auf Arch laufen:

```bash
cd aur
makepkg --printsrcinfo > .SRCINFO
makepkg -sf
namcap PKGBUILD
namcap *.pkg.tar.*
```

Auf Nicht-Arch-Systemen sind nur statische Checks sinnvoll; `makepkg`/`yay` darf dann nicht als bestanden gemeldet werden.

## Wichtige Dateien

- `streamdeck_app.py` – App/GUI
- `streamdeck` – Source-Checkout-Wrapper
- `install.sh` – lokale Installation
- `aur/PKGBUILD` – AUR-Packaging-Vorlage
- `icons/` – mitgelieferte Standard-Icons

## Lizenz

MIT – siehe `LICENSE`.
