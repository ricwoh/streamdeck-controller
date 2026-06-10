#!/usr/bin/env python3
"""Statische Packaging-Checks (laufen auf jedem System, kein Arch nötig)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_DEPS = ["python", "hidapi", "pyside6", "python-pillow",
                 "python-elgato-streamdeck", "python-requests"]
SOURCE = "streamdeck-controller::git+https://github.com/ricwoh/streamdeck-controller.git"


def fail(msg: str) -> None:
    raise SystemExit(f"FEHLER: {msg}")


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def check_python_syntax() -> None:
    for py in (ROOT / "streamdeck_controller").rglob("*.py"):
        ast.parse(py.read_text(encoding="utf-8"))
    ast.parse(read("tools/generate_icons.py"))


def pkgbuild_depends(text: str) -> list[str]:
    match = re.search(r"depends=\(([^)]*)\)", text, re.S)
    if not match:
        fail("depends=(...) fehlt im PKGBUILD")
    return [a or b for a, b in re.findall(r"'([^']+)'|\"([^\"]+)\"", match.group(1))]


def check_pkgbuild(path: str) -> None:
    text = read(path)
    if "pip install" in text:
        fail(f"{path}: pip install darf nicht im PKGBUILD stehen")
    if SOURCE not in text:
        fail(f"{path}: GitHub source fehlt/falsch")
    deps = pkgbuild_depends(text)
    for dep in EXPECTED_DEPS:
        if dep not in deps:
            fail(f"{path}: Dependency fehlt: {dep}")
    for bad in ["python-pyside6", "python-streamdeck", "streamdeck_app.py",
                "streamdeck_controller.py"]:
        if bad in text:
            fail(f"{path}: stale Referenz gefunden: {bad}")
    for needle in ["STREAMDECK_ICONS_DIR", "-m streamdeck_controller",
                   "data/streamdeck-controller.desktop",
                   "data/50-elgato-streamdeck.rules"]:
        if needle not in text:
            fail(f"{path}: erwartete Install-Referenz fehlt: {needle}")


def check_srcinfo(path: str) -> None:
    text = read(path)
    for dep in EXPECTED_DEPS:
        if f"depends = {dep}" not in text:
            fail(f"{path}: Dependency fehlt: {dep}")
    if f"source = {SOURCE}" not in text:
        fail(f"{path}: source fehlt/falsch")


def check_desktop() -> None:
    text = read("data/streamdeck-controller.desktop")
    for needle in ["Exec=streamdeck ui", "Type=Application"]:
        if needle not in text:
            fail(f"Desktop-Datei: fehlt {needle}")


def check_local_install() -> None:
    install = read("install.sh")
    wrapper = read("streamdeck")
    for text, name in [(install, "install.sh"), (wrapper, "streamdeck")]:
        if "streamdeck_controller" not in text:
            fail(f"{name}: Paketverweis streamdeck_controller fehlt")
        if "streamdeck_app.py" in text:
            fail(f"{name}: stale Referenz streamdeck_app.py")
    if "data/50-elgato-streamdeck.rules" not in install:
        fail("install.sh: udev-Regel fehlt")
    if "autostart on" not in install:
        fail("install.sh: Autostart-Schritt fehlt")


def check_icons() -> None:
    builtin = ROOT / "icons" / "builtin"
    if not builtin.is_dir() or len(list(builtin.glob("*.png"))) < 40:
        fail("icons/builtin fehlt oder unvollständig — tools/generate_icons.py ausführen")


def main() -> None:
    check_python_syntax()
    check_pkgbuild("aur/PKGBUILD")
    check_srcinfo("aur/.SRCINFO")
    check_desktop()
    check_local_install()
    check_icons()
    print("Statische Packaging-Checks: OK")


if __name__ == "__main__":
    main()
