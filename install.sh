#!/usr/bin/env bash
# Stream Deck Controller – local installer
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HOME/.venv/streamdeck"
APP="$SCRIPT_DIR/streamdeck_app.py"
BIN_DIR="$HOME/.local/bin"
BIN="$BIN_DIR/streamdeck-controller"
LEGACY_BIN="$BIN_DIR/streamdeck"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/streamdeck-controller.desktop"
UDEV_RULE="/etc/udev/rules.d/50-elgato-streamdeck.rules"

echo "=== Stream Deck Controller – Installer ==="

if command -v pacman >/dev/null 2>&1; then
  sudo pacman -S --needed --noconfirm python python-pip hidapi
elif command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y python3 python3-venv python3-pip libhidapi-libusb0
elif command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y python3 python3-pip hidapi
else
  echo "Unbekannte Distribution – bitte python3, venv/pip und hidapi manuell installieren."
fi

python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"

echo "→ udev-Regel installieren (sudo)"
sudo tee "$UDEV_RULE" >/dev/null <<'EOF'
SUBSYSTEM=="usb", ATTRS{idVendor}=="0fd9", TAG+="uaccess"
KERNEL=="hidraw*", ATTRS{idVendor}=="0fd9", TAG+="uaccess"
EOF
sudo udevadm control --reload-rules || true
sudo udevadm trigger || true

mkdir -p "$BIN_DIR"
cat > "$BIN" <<EOF
#!/usr/bin/env bash
export STREAMDECK_ICONS_DIR="$SCRIPT_DIR/icons"
exec "$VENV/bin/python3" "$APP" "\$@"
EOF
chmod 755 "$BIN"
ln -sf "$BIN" "$LEGACY_BIN"

mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=Stream Deck Controller
Comment=Elgato Stream Deck konfigurieren und steuern
Exec=$BIN
Icon=input-gaming
Terminal=false
Type=Application
Categories=Utility;HardwareSettings;
StartupNotify=true
EOF

echo "✓ Installation abgeschlossen"
echo "Start: streamdeck-controller"
echo "Geräte prüfen: streamdeck-controller --list-devices"
echo "Falls das Gerät nicht sichtbar ist: USB einmal trennen und neu verbinden."
