#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT/aur/aur-repo/PKGBUILD" ]]; then
  AUR_DIR="$ROOT/aur/aur-repo"
else
  AUR_DIR="$ROOT/aur"
fi
PKGBUILD="$AUR_DIR/PKGBUILD"
SRCINFO="$AUR_DIR/.SRCINFO"

fail() { printf 'FEHLER: %s\n' "$*" >&2; exit 1; }
ok() { printf 'OK: %s\n' "$*"; }
info() { printf 'INFO: %s\n' "$*"; }

usage() {
  cat <<'EOF'
Usage: tools/test-arch-package.sh [--require-runtime]

Runs the real Arch/AUR packaging check when an Arch runtime is available.
Supported runtimes:
  1. Native Arch host with makepkg
  2. Docker with archlinux:base-devel
  3. Podman with archlinux:base-devel

--require-runtime exits with failure when no runtime exists.
EOF
}

REQUIRE_RUNTIME=0
if [[ "${1:-}" == "--require-runtime" ]]; then
  REQUIRE_RUNTIME=1
elif [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
elif [[ -n "${1:-}" ]]; then
  usage >&2
  exit 64
fi

[[ -f "$PKGBUILD" ]] || fail "PKGBUILD fehlt: $PKGBUILD"
[[ -f "$SRCINFO" ]] || fail ".SRCINFO fehlt: $SRCINFO"

cd "$ROOT"
BRANCH="$(git branch --show-current 2>/dev/null || true)"
HEAD_SHA="$(git rev-parse HEAD 2>/dev/null || true)"

prepare_workdir() {
  local tmp="$1"
  git clone --bare "$ROOT" "$tmp/source.git" >/dev/null 2>&1
  mkdir -p "$tmp/aur"
  cp -a "$AUR_DIR" "$tmp/aur/aur-repo"
}

patch_pkgbuild_to_local_source() {
  local dir="$1"
  local pkg="$dir/aur/aur-repo/PKGBUILD"
  python3 - "$pkg" "$HEAD_SHA" <<'PY'
from pathlib import Path
import sys
pkg = Path(sys.argv[1])
head = sys.argv[2]
s = pkg.read_text()
old = 'source=("streamdeck-controller::git+https://github.com/ricwoh/streamdeck-controller.git")'
new = f'source=("streamdeck-controller::git+file:///work/source.git#commit={head}")'
if old not in s:
    raise SystemExit(f'expected source line not found in {pkg}')
pkg.write_text(s.replace(old, new))
PY
}

arch_commands_common='set -euo pipefail
pacman -Syu --noconfirm --needed git base-devel sudo namcap python pyside6 python-pillow hidapi
if ! id -u builder >/dev/null 2>&1; then useradd -m -u 1000 builder; fi
printf "builder ALL=(ALL) NOPASSWD: ALL\n" >/etc/sudoers.d/builder
chmod 440 /etc/sudoers.d/builder
chown -R builder:builder /work
su builder -c "git clone https://aur.archlinux.org/python-elgato-streamdeck.git /tmp/python-elgato-streamdeck"
su builder -c "cd /tmp/python-elgato-streamdeck && makepkg -si --noconfirm --needed"
su builder -c "cd /work/aur/aur-repo && makepkg --printsrcinfo > /tmp/generated.SRCINFO"
diff -u /work/aur/aur-repo/.SRCINFO /tmp/generated.SRCINFO
su builder -c "cd /work/aur/aur-repo && makepkg -sf --noconfirm"
su builder -c "cd /work/aur/aur-repo && namcap PKGBUILD && namcap ./*.pkg.tar.*"
'

run_native_makepkg() {
  info "Native makepkg gefunden: prüfe .SRCINFO und baue Paket"
  cd "$AUR_DIR"
  makepkg --printsrcinfo > /tmp/streamdeck-controller.SRCINFO
  diff -u .SRCINFO /tmp/streamdeck-controller.SRCINFO
  if command -v yay >/dev/null 2>&1; then
    yay -S --needed --noconfirm python-elgato-streamdeck || true
  fi
  makepkg -sf --noconfirm
  if command -v namcap >/dev/null 2>&1; then
    namcap PKGBUILD
    namcap ./*.pkg.tar.*
  else
    info "namcap nicht installiert: übersprungen"
  fi
  ok "Arch makepkg Build grün"
}

run_container() {
  local runtime="$1"
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  prepare_workdir "$tmp"

  # First verify committed PKGBUILD <-> .SRCINFO exactly as AUR sees it.
  info "Starte Arch Container via $runtime: .SRCINFO + Paketbuild"
  "$runtime" run --rm \
    -v "$tmp:/work" \
    -w /work/aur/aur-repo \
    archlinux:base-devel \
    bash -lc 'set -euo pipefail; pacman -Syu --noconfirm --needed base-devel git; makepkg --printsrcinfo > /tmp/generated.SRCINFO; diff -u .SRCINFO /tmp/generated.SRCINFO'
  ok ".SRCINFO stimmt mit PKGBUILD überein"

  # Then build current checked-out commit, not whatever GitHub main currently points to.
  patch_pkgbuild_to_local_source "$tmp"
  "$runtime" run --rm \
    -v "$tmp:/work" \
    -w /work \
    archlinux:base-devel \
    bash -lc "$arch_commands_common"
  ok "Arch Container Paketbuild grün für Commit ${HEAD_SHA:0:7}${BRANCH:+ auf Branch $BRANCH}"
}

if command -v makepkg >/dev/null 2>&1; then
  run_native_makepkg
  exit 0
fi

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  run_container docker
  exit 0
fi

if command -v podman >/dev/null 2>&1; then
  run_container podman
  exit 0
fi

msg="Kein Arch Runtime gefunden: brauche native Arch makepkg, Docker oder Podman. Setup-Hilfe: tools/setup-arch-test-runtime.sh"
if [[ "$REQUIRE_RUNTIME" -eq 1 ]]; then
  fail "$msg"
fi
info "$msg"
exit 2
