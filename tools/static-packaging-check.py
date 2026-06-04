#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_DEPS = ["python", "hidapi", "pyside6", "python-pillow", "python-elgato-streamdeck"]
SOURCE = "streamdeck-controller::git+https://github.com/ricwoh/streamdeck-controller.git"


def fail(msg: str) -> None:
    raise SystemExit(f"FEHLER: {msg}")


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def pkgbuild_depends(text: str) -> list[tuple[str, str]]:
    match = re.search(r"depends=\(([^)]*)\)", text, re.S)
    if not match:
        fail("depends=(...) fehlt im PKGBUILD")
    return re.findall(r"'([^']+)'|\"([^\"]+)\"", match.group(1))


def flatten(matches: list[tuple[str, str]]) -> list[str]:
    return [a or b for a, b in matches]


def check_python_syntax() -> None:
    ast.parse(read("streamdeck_app.py"))


def check_pkgbuild(path: str) -> None:
    text = read(path)
    if "pip install" in text:
        fail(f"{path}: pip install darf nicht im PKGBUILD stehen")
    if SOURCE not in text:
        fail(f"{path}: GitHub source fehlt/falsch")
    deps = flatten(pkgbuild_depends(text))
    for dep in EXPECTED_DEPS:
        if dep not in deps:
            fail(f"{path}: Dependency fehlt: {dep}")
    stale = ["python-pyside6", "python-streamdeck", "streamdeck_controller.py"]
    for bad in stale:
        if bad in text:
            fail(f"{path}: stale Referenz gefunden: {bad}")
    for needle in ["STREAMDECK_ICONS_DIR", "streamdeck_app.py", "Exec=streamdeck-controller"]:
        if needle not in text:
            fail(f"{path}: erwartete Install-Referenz fehlt: {needle}")


def check_srcinfo() -> None:
    text = read("aur/aur-repo/.SRCINFO")
    for dep in EXPECTED_DEPS:
        if f"depends = {dep}" not in text:
            fail(f".SRCINFO: Dependency fehlt: {dep}")
    for bad in ["python-pyside6", "python-streamdeck"]:
        if bad in text:
            fail(f".SRCINFO: stale Dependency gefunden: {bad}")
    if f"source = {SOURCE}" not in text:
        fail(".SRCINFO: source fehlt/falsch")


def check_desktop() -> None:
    text = read("appimage/streamdeck.desktop")
    for needle in ["Exec=streamdeck-controller", "Type=Application", "Categories=Utility;HardwareSettings;"]:
        if needle not in text:
            fail(f"Desktop-Datei: fehlt {needle}")


def check_local_install() -> None:
    install = read("install.sh")
    wrapper = read("streamdeck")
    for text, name in [(install, "install.sh"), (wrapper, "streamdeck")]:
        if "streamdeck_app.py" not in text:
            fail(f"{name}: streamdeck_app.py fehlt")
        if "streamdeck_controller.py" in text:
            fail(f"{name}: alte streamdeck_controller.py Referenz")


def main() -> None:
    check_python_syntax()
    check_local_install()
    check_pkgbuild("aur/PKGBUILD")
    check_pkgbuild("aur/aur-repo/PKGBUILD")
    check_srcinfo()
    check_desktop()
    print("OK: static packaging check")


if __name__ == "__main__":
    main()
