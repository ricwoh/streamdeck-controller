#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ARCH_MODE="auto"
case "${1:-}" in
  --arch) ARCH_MODE="required" ;;
  --no-arch) ARCH_MODE="skip" ;;
  -h|--help)
    cat <<'EOF'
Usage: tools/release-check.sh [--arch|--no-arch]

Default: run source/static checks and run Arch package check automatically
when makepkg/Docker/Podman is available.

--arch    require the real Arch package check, fail if no runtime exists
--no-arch skip the real Arch package check
EOF
    exit 0
    ;;
  "") ;;
  *) printf 'FEHLER: unbekannte Option: %s\n' "$1" >&2; exit 64 ;;
esac

ok() { printf 'OK: %s\n' "$*"; }
fail() { printf 'FEHLER: %s\n' "$*" >&2; exit 1; }
info() { printf 'INFO: %s\n' "$*"; }

printf '== streamdeck-controller release check ==\n'

[ -d .git ] || fail "Nicht im Git-Repo: $ROOT"
branch="$(git branch --show-current)"
[ -n "$branch" ] || fail "Kein aktiver Git-Branch"
ok "Branch: $branch"

remote="$(git remote get-url origin 2>/dev/null || true)"
[ -n "$remote" ] || fail "Git remote origin fehlt"
case "$remote" in
  git@github.com:ricwoh/streamdeck-controller.git|https://github.com/ricwoh/streamdeck-controller.git) ok "Remote: $remote" ;;
  *) fail "Unerwarteter Remote: $remote" ;;
esac

status="$(git status --short)"
if [ -n "$status" ]; then
  info "Uncommitted/untracked Dateien vorhanden:"
  printf '%s\n' "$status"
else
  ok "Git working tree sauber"
fi

bad_artifacts="$(find . \
  -path './.git' -prune -o \
  -path './.venv' -prune -o \
  -path './venv' -prune -o \
  -path './.pytest_cache' -prune -o \
  \( -path './aur/aur-repo/pkg' -o -path './aur/aur-repo/src' -o -name '*.pkg.tar.*' -o -name '.env' -o -name '*.log' \) -print)"
[ -z "$bad_artifacts" ] || fail "Lokale Secrets/Build-Artefakte gefunden:\n$bad_artifacts"
ok "Keine offensichtlichen Build-Artefakte/Secrets"

secret_hits="$(git grep -nE '(OPENAI_API_KEY|VOICE_TOOLS_OPENAI_KEY|TELEGRAM_BOT_TOKEN|GITHUB_TOKEN|BEGIN (RSA|OPENSSH) PRIVATE KEY|password\s*=\s*[^[:space:]]+)' -- ':!tools/release-check.sh' ':!README.md' || true)"
[ -z "$secret_hits" ] || fail "Mögliche Secrets im Repo:\n$secret_hits"
ok "Secret-Scan sauber"

python3 -m compileall -q streamdeck_controller
ok "Python Syntax ok"

if [ -f requirements.txt ]; then
  ok "requirements.txt vorhanden"
fi

python3 -m pytest -q
ok "Tests grün"

python3 tools/static-packaging-check.py
ok "Statische Packaging-Checks grün"

case "$ARCH_MODE" in
  skip)
    info "Arch/AUR-Build übersprungen (--no-arch)"
    printf '\nERGEBNIS: OK für Source/Static-Checks. Arch/AUR-Build wurde übersprungen.\n'
    ;;
  required)
    ./tools/test-arch-package.sh --require-runtime
    printf '\nERGEBNIS: OK inklusive echtem Arch/AUR-Paketbuild.\n'
    ;;
  auto)
    if ./tools/test-arch-package.sh; then
      printf '\nERGEBNIS: OK inklusive echtem Arch/AUR-Paketbuild.\n'
    else
      code="$?"
      if [[ "$code" -eq 2 ]]; then
        printf '\nERGEBNIS: OK für Source/Static-Checks. Finaler Arch/AUR-Build braucht makepkg, Docker oder Podman.\n'
      else
        exit "$code"
      fi
    fi
    ;;
esac
