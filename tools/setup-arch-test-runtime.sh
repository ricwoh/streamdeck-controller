#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=""
elif command -v sudo >/dev/null 2>&1; then
  SUDO="sudo"
else
  echo "FEHLER: sudo fehlt. Bitte als root ausführen." >&2
  exit 1
fi

. /etc/os-release
case "${ID:-}" in
  ubuntu|debian)
    $SUDO apt-get update
    $SUDO apt-get install -y podman uidmap slirp4netns fuse-overlayfs
    ;;
  arch)
    $SUDO pacman -Syu --noconfirm --needed podman
    ;;
  *)
    echo "FEHLER: Nicht unterstütztes OS: ${PRETTY_NAME:-unknown}" >&2
    exit 1
    ;;
esac

podman pull archlinux:base-devel

echo "OK: Arch-Testruntime bereit. Teste jetzt mit:"
echo "  cd ~/Programmieren/Projekte/streamdeck && ./tools/test-arch-package.sh"
