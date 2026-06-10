"""Terminal-Befehl `streamdeck` — ohne Argumente werden alle Befehle angezeigt."""

import os
import subprocess
import sys
import time

from . import __version__
from . import autostart
from .ipc import daemon_running, ipc_request
from .paths import CONFIG_PATH, LOG_PATH

HELP = f"""\
Stream Deck Controller {__version__}

Verwendung: streamdeck <befehl>

Daemon (Hintergrunddienst, steuert das Deck):
  run            Daemon im Vordergrund starten (Logs im Terminal)
  start          Daemon im Hintergrund starten
  stop           Daemon stoppen
  restart        Daemon neu starten
  status         Status anzeigen (Gerät, Seite, Spotify)

App:
  ui             Konfigurations-App (GUI) öffnen
  devices        Angeschlossene Stream Decks auflisten
  log            Log live anzeigen
  config         Konfigurationsdatei im Editor öffnen

Spotify:
  spotify login    Bei Spotify anmelden (Browser öffnet sich)
  spotify status   Verbindungsstatus anzeigen
  spotify logout   Anmeldung entfernen

Autostart:
  autostart on     Beim Hochfahren automatisch starten (systemd)
  autostart off    Autostart deaktivieren
  autostart status Autostart-Status anzeigen

Sonstiges:
  version        Version anzeigen
  help           Diese Hilfe anzeigen
"""


def _print_help() -> int:
    print(HELP)
    return 0


def _cmd_run() -> int:
    from .daemon import run_daemon
    run_daemon()
    return 0


def _cmd_start() -> int:
    if daemon_running():
        print("Daemon läuft bereits.")
        return 0
    if autostart.is_installed():
        autostart.start()
        print("Daemon über systemd gestartet.")
        return 0
    with open(LOG_PATH, "a") as logfile:
        subprocess.Popen(
            [sys.executable, "-m", "streamdeck_controller", "run"],
            stdout=logfile, stderr=logfile,
            start_new_session=True,
        )
    time.sleep(1.0)
    print("Daemon gestartet." if daemon_running() else
          f"Start ausgelöst — Status mit: streamdeck status (Log: {LOG_PATH})")
    return 0


def _cmd_stop() -> int:
    if autostart.is_installed() and autostart.is_active():
        autostart.stop()
        print("Daemon über systemd gestoppt.")
        return 0
    if ipc_request({"cmd": "stop"}):
        print("Daemon gestoppt.")
        return 0
    print("Daemon läuft nicht.")
    return 0


def _cmd_restart() -> int:
    if autostart.is_installed():
        autostart.restart()
        print("Daemon über systemd neu gestartet.")
        return 0
    _cmd_stop()
    time.sleep(1.0)
    return _cmd_start()


def _cmd_status() -> int:
    response = ipc_request({"cmd": "status"})
    if not response:
        print("● Daemon: läuft nicht  (starten mit: streamdeck start)")
        return 1
    device = response.get("device") or {}
    connected = response.get("connected")
    print(f"● Daemon: läuft (v{response.get('version', '?')})")
    if connected:
        print(f"● Deck:   {device.get('type', '?')} — {device.get('keys', '?')} Tasten"
              f" (Serial {device.get('serial', '?')})")
    else:
        print("● Deck:   nicht verbunden (USB prüfen)")
    pages = response.get("pages", [])
    page_idx = response.get("page", 0)
    page_name = pages[page_idx] if page_idx < len(pages) else "?"
    print(f"● Seite:  {page_idx + 1}/{len(pages)} ({page_name})")
    print(f"● Spotify: {'verbunden' if response.get('spotify_ready') else 'nicht verbunden'}")
    return 0


def _cmd_ui() -> int:
    from .gui.app import run_gui
    return run_gui()


def _cmd_devices() -> int:
    from .deck.manager import list_devices_info
    infos = list_devices_info()
    if not infos:
        print("Keine Stream-Deck-Geräte gefunden.")
        print("Tipp: udev-Regel installiert? (install.sh oder README)")
        return 1
    for i, info in enumerate(infos):
        print(f"{i}: {info['type']} — {info['keys']} Tasten "
              f"({info['cols']}x{info['rows']}), Serial: {info['serial']}")
    return 0


def _cmd_log() -> int:
    if not LOG_PATH.exists():
        print(f"Noch kein Log unter {LOG_PATH}")
        return 1
    return subprocess.call(["tail", "-f", str(LOG_PATH)])


def _cmd_config() -> int:
    from .config import load_config, save_config
    if not CONFIG_PATH.exists():
        save_config(load_config())
    editor = os.environ.get("EDITOR")
    return subprocess.call([editor, str(CONFIG_PATH)] if editor
                           else ["xdg-open", str(CONFIG_PATH)])


def _cmd_spotify(args: list[str]) -> int:
    from .config import load_config, save_config
    from .spotify import SpotifyClient, auth

    sub = args[0] if args else "status"
    cfg = load_config()
    sp_cfg = cfg.get("spotify", {})

    if sub == "login":
        client_id = sp_cfg.get("client_id", "")
        if not client_id:
            print("Es fehlt noch eine Spotify Client-ID. So bekommst du sie (einmalig):")
            print("  1. https://developer.spotify.com/dashboard öffnen und einloggen")
            print("  2. 'Create app' — Name egal, Redirect URI: http://127.0.0.1:8888/callback")
            print("  3. API auswählen: Web API")
            print("  4. Die Client-ID aus den App-Einstellungen kopieren\n")
            client_id = input("Client-ID hier einfügen: ").strip()
            if not client_id:
                print("Abgebrochen.")
                return 1
            cfg["spotify"]["client_id"] = client_id
            save_config(cfg)
        try:
            auth.login(client_id,
                       sp_cfg.get("redirect_uri", "http://127.0.0.1:8888/callback"))
        except RuntimeError as e:
            print(f"Fehler: {e}")
            return 1
        print("✅ Spotify verbunden!")
        ipc_request({"cmd": "reload"})
        return 0

    if sub == "logout":
        auth.clear_token()
        ipc_request({"cmd": "reload"})
        print("Spotify-Anmeldung entfernt.")
        return 0

    client = SpotifyClient(sp_cfg.get("client_id", ""))
    if client.ready:
        info = client.current_song_info()
        print("● Spotify: verbunden")
        print(f"● Läuft gerade: {info or 'nichts'}")
    else:
        print("● Spotify: nicht verbunden — anmelden mit: streamdeck spotify login")
    return 0


def _cmd_autostart(args: list[str]) -> int:
    sub = args[0] if args else "status"
    if sub == "on":
        path = autostart.install()
        print(f"Autostart aktiviert ({path}).\nDer Daemon startet ab jetzt mit der Anmeldung.")
        return 0
    if sub == "off":
        autostart.uninstall()
        print("Autostart deaktiviert.")
        return 0
    if autostart.is_installed():
        print(f"● Autostart: {'aktiviert' if autostart.is_enabled() else 'installiert, aber deaktiviert'}")
        print(f"● Dienst:    {'läuft' if autostart.is_active() else 'gestoppt'}")
    else:
        print("● Autostart: nicht eingerichtet (aktivieren mit: streamdeck autostart on)")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = args.pop(0) if args else "help"

    if cmd in ("help", "--help", "-h"):
        return _print_help()
    if cmd in ("version", "--version"):
        print(f"streamdeck-controller {__version__}")
        return 0
    if cmd == "run":
        return _cmd_run()
    if cmd == "start":
        return _cmd_start()
    if cmd == "stop":
        return _cmd_stop()
    if cmd == "restart":
        return _cmd_restart()
    if cmd == "status":
        return _cmd_status()
    if cmd in ("ui", "gui", "app"):
        return _cmd_ui()
    if cmd in ("devices", "list-devices", "--list-devices"):
        return _cmd_devices()
    if cmd == "log":
        return _cmd_log()
    if cmd == "config":
        return _cmd_config()
    if cmd == "spotify":
        return _cmd_spotify(args)
    if cmd == "autostart":
        return _cmd_autostart(args)

    print(f"Unbekannter Befehl: {cmd}\n")
    return _print_help() or 2


if __name__ == "__main__":
    sys.exit(main())
