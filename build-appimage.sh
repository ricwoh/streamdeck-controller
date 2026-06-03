#!/bin/bash
# Stream Deck Controller – AppImage bauen
# Voraussetzungen: venv unter ~/.venv/streamdeck muss existieren (install.sh)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HOME/.venv/streamdeck"
BUILD_DIR="$SCRIPT_DIR/build"
APPDIR="$BUILD_DIR/AppDir"
OUT="$SCRIPT_DIR/StreamDeck-Controller-x86_64.AppImage"

echo "=== Stream Deck AppImage Builder ==="
echo

# ── Voraussetzungen prüfen ────────────────────────────────────────────────────
if [ ! -d "$VENV" ]; then
    echo "Fehler: venv nicht gefunden. Bitte zuerst install.sh ausführen."
    exit 1
fi

# PyInstaller installieren falls nötig
if ! "$VENV/bin/python3" -c "import PyInstaller" 2>/dev/null; then
    echo "→ PyInstaller installieren..."
    "$VENV/bin/pip" install --quiet pyinstaller
fi

# appimagetool holen falls nicht vorhanden
APPIMAGETOOL="$(command -v appimagetool 2>/dev/null || echo "$BUILD_DIR/appimagetool")"
if [ ! -f "$APPIMAGETOOL" ] && ! command -v appimagetool &>/dev/null; then
    echo "→ appimagetool herunterladen..."
    mkdir -p "$BUILD_DIR"
    curl -L -o "$BUILD_DIR/appimagetool" \
        "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$BUILD_DIR/appimagetool"
    APPIMAGETOOL="$BUILD_DIR/appimagetool"
fi

# ── PyInstaller: Controller bundlen ──────────────────────────────────────────
echo "→ PyInstaller: Controller bundlen..."
cd "$SCRIPT_DIR"

HIDAPI_LIB="$(find /usr/lib -name 'libhidapi-libusb.so.0' 2>/dev/null | head -1)"
if [ -z "$HIDAPI_LIB" ]; then
    echo "Fehler: libhidapi-libusb.so.0 nicht gefunden. Bitte hidapi installieren."
    exit 1
fi

"$VENV/bin/pyinstaller" \
    --onefile \
    --name streamdeck-controller \
    --distpath "$BUILD_DIR/dist" \
    --workpath "$BUILD_DIR/work" \
    --specpath "$BUILD_DIR" \
    --add-binary "$HIDAPI_LIB:." \
    --hidden-import PIL \
    --hidden-import PIL.Image \
    --hidden-import PIL.ImageDraw \
    --hidden-import PIL.ImageFont \
    --hidden-import PySide6 \
    --hidden-import PySide6.QtCore \
    --hidden-import PySide6.QtGui \
    --hidden-import PySide6.QtWidgets \
    --hidden-import StreamDeck \
    --hidden-import StreamDeck.DeviceManager \
    --hidden-import StreamDeck.Transport.LibUSBHIDAPI \
    --hidden-import StreamDeck.ImageHelpers \
    streamdeck_app.py

echo "  ✓ Binary gebaut: $BUILD_DIR/dist/streamdeck-controller"

# ── AppDir-Struktur aufbauen ──────────────────────────────────────────────────
echo "→ AppDir aufbauen..."
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/lib"

# Executable
cp "$BUILD_DIR/dist/streamdeck-controller" "$APPDIR/usr/bin/"

# libhidapi separat mitliefern (als Fallback falls im Bundle nicht gefunden)
cp "$HIDAPI_LIB" "$APPDIR/usr/lib/"

# AppRun, Desktop-Datei, Icon
cp "$SCRIPT_DIR/appimage/AppRun" "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"
cp "$SCRIPT_DIR/appimage/streamdeck.desktop" "$APPDIR/"

# Icon: System-Icon kopieren oder Platzhalter
ICON_SRC="$(find /usr/share/icons -name "input-gaming*" 2>/dev/null | head -1)"
if [ -n "$ICON_SRC" ]; then
    cp "$ICON_SRC" "$APPDIR/streamdeck.png" 2>/dev/null || \
    convert "$ICON_SRC" "$APPDIR/streamdeck.png" 2>/dev/null || true
fi

# Fallback: leeres Icon erstellen (verhindert Fehler bei appimagetool)
if [ ! -f "$APPDIR/streamdeck.png" ]; then
    "$VENV/bin/python3" -c "
from PIL import Image, ImageDraw
img = Image.new('RGBA', (256, 256), (30, 30, 30, 255))
d = ImageDraw.Draw(img)
d.rectangle([40, 40, 216, 216], fill=(80, 120, 200, 255))
d.text((90, 110), 'SD', fill=(255, 255, 255, 255))
img.save('$APPDIR/streamdeck.png')
"
fi

# ── AppImage packen ───────────────────────────────────────────────────────────
echo "→ AppImage packen..."
ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$OUT"

echo
echo "✓ AppImage fertig: $OUT"
echo
echo "  Verwendung:"
echo "    chmod +x $OUT"
echo "    $OUT"
echo
echo "  Hinweis: Beim ersten Start wird automatisch nach der udev-Regel gefragt."
