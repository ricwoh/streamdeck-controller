"""Autostart über einen systemd-User-Service — verlässlich und schnell."""

import shutil
import subprocess
import sys
from pathlib import Path

SERVICE_NAME = "streamdeck-daemon.service"
SERVICE_DIR = Path.home() / ".config" / "systemd" / "user"
SERVICE_PATH = SERVICE_DIR / SERVICE_NAME

SERVICE_TEMPLATE = """\
[Unit]
Description=Stream Deck Daemon
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=on-failure
RestartSec=3

[Install]
WantedBy=graphical-session.target
"""


def _systemctl(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["systemctl", "--user", *args],
                          capture_output=True, text=True)


def _exec_start() -> str:
    """Startbefehl: installierter Launcher, sonst aktueller Python-Interpreter."""
    launcher = shutil.which("streamdeck")
    if launcher:
        return f"{launcher} run"
    return f"{sys.executable} -m streamdeck_controller run"


def install(enable_now: bool = True) -> str:
    SERVICE_DIR.mkdir(parents=True, exist_ok=True)
    SERVICE_PATH.write_text(SERVICE_TEMPLATE.format(exec_start=_exec_start()))
    _systemctl("daemon-reload")
    _systemctl("enable", SERVICE_NAME)
    if enable_now:
        _systemctl("restart", SERVICE_NAME)
    return str(SERVICE_PATH)


def uninstall():
    _systemctl("disable", "--now", SERVICE_NAME)
    SERVICE_PATH.unlink(missing_ok=True)
    _systemctl("daemon-reload")


def is_installed() -> bool:
    return SERVICE_PATH.exists()


def is_enabled() -> bool:
    return _systemctl("is-enabled", SERVICE_NAME).stdout.strip() == "enabled"


def is_active() -> bool:
    return _systemctl("is-active", SERVICE_NAME).stdout.strip() == "active"


def start():
    return _systemctl("start", SERVICE_NAME)


def stop():
    return _systemctl("stop", SERVICE_NAME)


def restart():
    return _systemctl("restart", SERVICE_NAME)
