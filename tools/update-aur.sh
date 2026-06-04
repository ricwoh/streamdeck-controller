#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ok() { printf 'OK: %s\n' "$*"; }
fail() { printf 'FEHLER: %s\n' "$*" >&2; exit 1; }
info() { printf 'INFO: %s\n' "$*"; }

printf '== streamdeck-controller AUR sync ==\n'

[ -f aur/PKGBUILD ] || fail "aur/PKGBUILD fehlt"
[ -d aur/aur-repo ] || fail "aur/aur-repo fehlt"
[ -f aur/aur-repo/PKGBUILD ] || fail "aur/aur-repo/PKGBUILD fehlt"

cp aur/PKGBUILD aur/aur-repo/PKGBUILD
cp aur/streamdeck-controller.install aur/aur-repo/streamdeck-controller.install
ok "AUR Arbeitskopie aus Template synchronisiert"

python3 tools/static-packaging-check.py
ok "Statische Packaging-Prüfung grün"

if command -v makepkg >/dev/null 2>&1; then
  (cd aur/aur-repo && makepkg --printsrcinfo > .SRCINFO)
  cp aur/aur-repo/.SRCINFO aur/.SRCINFO
  ok ".SRCINFO mit makepkg neu erzeugt und Template aktualisiert"
else
  info "makepkg nicht vorhanden: .SRCINFO bleibt unverändert. Regenerieren auf Arch mit: cd aur/aur-repo && makepkg --printsrcinfo > .SRCINFO && cp .SRCINFO ../.SRCINFO"
fi

rm -rf aur/aur-repo/pkg aur/aur-repo/src aur/aur-repo/streamdeck-controller aur/aur-repo/*.pkg.tar.*
ok "AUR Build-Artefakte entfernt"

printf '\nNÄCHSTER SCHRITT AUF ARCH:\n'
printf 'cd ~/Programmieren/Projekte/streamdeck/aur/aur-repo && makepkg --printsrcinfo > .SRCINFO && makepkg -sf\n'
printf '\nDanach erst committen/pushen.\n'
