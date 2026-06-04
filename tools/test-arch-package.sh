#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if command -v makepkg >/dev/null 2>&1; then
  cd aur/aur-repo
  makepkg --printsrcinfo > .SRCINFO
  makepkg -sf
  if command -v namcap >/dev/null 2>&1; then
    namcap PKGBUILD
    namcap ./*.pkg.tar.*
  fi
  exit 0
fi

if command -v docker >/dev/null 2>&1; then
  echo "INFO: Docker gefunden, aber Arch-Build aus Ubuntu ist hier noch nicht aktiviert. Nutze besser Rico's Arch-PC für yay/makepkg."
  exit 2
fi

if command -v podman >/dev/null 2>&1; then
  echo "INFO: Podman gefunden, aber Arch-Build aus Ubuntu ist hier noch nicht aktiviert. Nutze besser Rico's Arch-PC für yay/makepkg."
  exit 2
fi

echo "FEHLER: Kein makepkg/docker/podman vorhanden. Echter Arch-Pakettest muss auf Arch laufen."
exit 2
