#!/bin/bash
# Stream Deck Controller – Installer
# Unterstützt Arch Linux, Debian/Ubuntu, Fedora
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HOME/.venv/streamdeck"
CONTROLLER="$SCRIPT_DIR/streamdeck_controller.py"
BIN_LINK="$HOME/.local/bin/streamdeck"
UDEV_RULE="/etc/udev/rules.d/50-elgato-streamdeck.rules"
DESKTOP_FILE="$HOME/.local/share/applications/streamdeck.desktop"

echo "=== Stream Deck Controller – Installer ==="
echo

# ── 1. System-Abhängigkeiten ──────────────────────────────────────────────────
echo "→ System-Abhängigkeiten prüfen..."
if command -v pacman &>/dev/null; then
    sudo pacman -S --needed --noconfirm python hidapi
elif command -v apt-get &>/dev/null; then
    sudo apt-get install -y python3 python3-venv libhidapi-libusb0
elif command -v dnf &>/dev/null; then
    sudo dnf install -y python3 python3-virtualenv hidapi
else
    echo "  Unbekannte Distribution – bitte folgende Pakete manuell installieren:"
    echo "    python3, python3-venv, libhidapi-libusb"
fi

# ── 2. Python-Umgebung ────────────────────────────────────────────────────────
echo "→ Python-Umgebung einrichten ($VENV)..."
python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet pillow streamdeck
echo "  ✓ pillow + streamdeck installiert"

# ── 3. udev-Regel ─────────────────────────────────────────────────────────────
echo "→ udev-Regel installieren (benötigt sudo)..."
sudo tee "$UDEV_RULE" > /dev/null << 'EOF'
# Elgato Stream Deck – Zugriff ohne root
SUBSYSTEM=="usb", ATTRS{idVendor}=="0fd9", TAG+="uaccess"
KERNEL=="hidraw*", ATTRS{idVendor}=="0fd9", TAG+="uaccess"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger
echo "  ✓ udev-Regel aktiv ($UDEV_RULE)"

# ── 4. Befehl in PATH ────────────────────────────────────────────────────────
mkdir -p "$HOME/.local/bin"
ln -sf "$SCRIPT_DIR/streamdeck" "$BIN_LINK"
chmod +x "$SCRIPT_DIR/streamdeck"
echo "→ Befehl 'streamdeck' verlinkt nach $BIN_LINK"

# PATH-Hinweis falls nötig
if ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    echo "  Hinweis: Füge folgendes zu deiner ~/.bashrc oder ~/.zshrc hinzu:"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# ── 5. Desktop-Eintrag ────────────────────────────────────────────────────────
mkdir -p "$HOME/.local/share/applications"
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=Stream Deck
Comment=Elgato Stream Deck Controller
Exec=$VENV/bin/python3 $CONTROLLER
Icon=input-gaming
Terminal=false
Type=Application
Categories=Utility;HardwareSettings;
StartupNotify=false
EOF
echo "→ Desktop-Eintrag erstellt ($DESKTOP_FILE)"

# ── Fertig ────────────────────────────────────────────────────────────────────
echo
echo "✓ Installation abgeschlossen!"
echo
echo "  Starten:        streamdeck run"
echo "  Hintergrund:    streamdeck start"
echo "  Status:         streamdeck status"
echo "  Log:            streamdeck log"
echo
echo "  Hinweis: Stream Deck USB einmal trennen und wieder einstecken,"
echo "           falls er beim ersten Start nicht erkannt wird."
