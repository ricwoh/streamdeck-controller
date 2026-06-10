#!/usr/bin/env bash
# Stream Deck Controller — lokaler Installer (Arch, Debian/Ubuntu, Fedora)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HOME/.venv/streamdeck"
BIN_DIR="$HOME/.local/bin"
BIN="$BIN_DIR/streamdeck"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/streamdeck-controller.desktop"
UDEV_RULE="/etc/udev/rules.d/50-elgato-streamdeck.rules"

echo "=== Stream Deck Controller — Installer ==="

if command -v pacman >/dev/null 2>&1; then
  sudo pacman -S --needed --noconfirm python hidapi
elif command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y python3 python3-venv libhidapi-libusb0
elif command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y python3 hidapi
else
  echo "Unbekannte Distribution — bitte python3, venv und hidapi manuell installieren."
fi

echo "→ Python-Umgebung unter $VENV"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"

echo "→ udev-Regel installieren (sudo)"
sudo cp "$SCRIPT_DIR/data/50-elgato-streamdeck.rules" "$UDEV_RULE"
sudo udevadm control --reload-rules || true
sudo udevadm trigger || true

echo "→ Starter unter $BIN"
mkdir -p "$BIN_DIR"
cat > "$BIN" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="$SCRIPT_DIR\${PYTHONPATH:+:\$PYTHONPATH}"
export STREAMDECK_ICONS_DIR="$SCRIPT_DIR/icons"
exec "$VENV/bin/python3" -m streamdeck_controller "\$@"
EOF
chmod 755 "$BIN"

mkdir -p "$DESKTOP_DIR"
sed "s|^Exec=.*|Exec=$BIN ui|" "$SCRIPT_DIR/data/streamdeck-controller.desktop" > "$DESKTOP_FILE"

echo "→ Autostart einrichten (systemd --user)"
"$BIN" autostart on || echo "  (Autostart später aktivierbar mit: streamdeck autostart on)"

echo
echo "✓ Installation abgeschlossen"
echo "  GUI öffnen:      streamdeck ui"
echo "  Alle Befehle:    streamdeck"
echo "  Geräte prüfen:   streamdeck devices"
echo "Falls das Deck nicht erkannt wird: USB einmal trennen und neu verbinden."
