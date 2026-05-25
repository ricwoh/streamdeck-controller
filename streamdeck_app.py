#!/usr/bin/env python3
"""Stream Deck – GUI-Konfigurator und Controller"""

import json, os, sys, time, subprocess, shutil, logging
from pathlib import Path
from copy import deepcopy

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QComboBox, QLineEdit, QFileDialog,
    QGroupBox, QMessageBox, QDialog, QTabWidget, QFrame, QScrollArea,
    QSizePolicy, QSpacerItem, QDialogButtonBox, QCheckBox, QSpinBox,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtGui import QPixmap, QIcon, QImage, QColor, QPainter, QFont

from PIL import Image, ImageDraw, ImageFont as PilFont, ImageEnhance
import StreamDeck.DeviceManager as DM
from StreamDeck.ImageHelpers import PILHelper
from StreamDeck.Transport.Transport import TransportError

# ── Pfade ──────────────────────────────────────────────────────────────────────
CONFIG_PATH = Path.home() / ".config" / "streamdeck" / "config.json"
ICONS_DIR   = Path(__file__).parent / "Icons"
LOG_PATH    = Path.home() / ".streamdeck.log"
FONT_PATH   = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
INSTANCE_KEY = "streamdeck-app-v1"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler(sys.stderr)],
)
log = logging.getLogger(__name__)

# ── Funktions-Bibliothek ────────────────────────────────────────────────────────
# (Kategorie, ID, Anzeige-Name, Aktion-Template, ist-Toggle)
FUNCTION_LIBRARY = [
    ("Spotify",  "spotify_play_pause",  "Play / Pause",        {"type": "spotify_dbus", "command": "play_pause"},                          True),
    ("Spotify",  "spotify_next",        "Nächster Song",       {"type": "spotify_dbus", "command": "next"},                                False),
    ("Spotify",  "spotify_prev",        "Vorheriger Song",     {"type": "spotify_dbus", "command": "previous"},                            False),
    ("Spotify",  "spotify_vol_up",      "Lauter (+5%)",        {"type": "spotify_dbus", "command": "volume_up"},                           False),
    ("Spotify",  "spotify_vol_down",    "Leiser (-5%)",        {"type": "spotify_dbus", "command": "volume_down"},                         False),
    ("Spotify",  "spotify_open",        "Spotify öffnen",      {"type": "spotify_dbus", "command": "open_spotify"},                        False),
    ("Spotify",  "spotify_song_info",   "Song-Info kopieren",  {"type": "song_info_clipboard"},                                            False),
    ("System",   "sys_vol_up",          "Lautstärke +",        {"type": "command", "cmd": "pactl set-sink-volume @DEFAULT_SINK@ +5%"},     False),
    ("System",   "sys_vol_down",        "Lautstärke -",        {"type": "command", "cmd": "pactl set-sink-volume @DEFAULT_SINK@ -5%"},     False),
    ("System",   "sys_mute",            "Stummschalten",       {"type": "command", "cmd": "pactl set-sink-mute @DEFAULT_SINK@ toggle"},    True),
    ("System",   "sys_mic_mute",        "Mikro stummschalten", {"type": "command", "cmd": "pactl set-source-mute @DEFAULT_SOURCE@ toggle"},True),
    ("System",   "sys_screenshot",      "Screenshot",          {"type": "command", "cmd": "flameshot gui"},                                False),
    ("System",   "sys_lock",            "Sperren",             {"type": "command", "cmd": "loginctl lock-session"},                        False),
    ("System",   "sys_suspend",         "Standby",             {"type": "command", "cmd": "systemctl suspend"},                            False),
    ("System",   "sys_brightness_up",   "Helligkeit +",        {"type": "command", "cmd": "brightnessctl set +10%"},                       False),
    ("System",   "sys_brightness_down", "Helligkeit -",        {"type": "command", "cmd": "brightnessctl set 10%-"},                       False),
    ("App",      "app_launch",          "App starten",         {"type": "command", "cmd": ""},                                             False),
    ("App",      "open_url",            "URL öffnen",          {"type": "command", "cmd": "xdg-open https://"},                            False),
    ("App",      "open_folder",         "Ordner öffnen",       {"type": "command", "cmd": "xdg-open ~/"},                                  False),
    ("Seiten",   "page_switch",         "Seite wechseln",      {"type": "page", "target": 0},                                              False),
    ("Sonstige", "custom_cmd",          "Eigener Befehl",      {"type": "command", "cmd": ""},                                             False),
    ("Sonstige", "none",                "— Keine Funktion —",  None,                                                                       False),
]
FN_BY_ID = {fn[1]: fn for fn in FUNCTION_LIBRARY}

DEFAULT_CONFIG = {
    "brightness": 80,
    "spotify_api": {"client_id": "", "client_secret": "", "redirect_uri": "http://localhost:8888/callback"},
    "pages": [{"name": "Hauptseite", "keys": {}}],
}

# ── Hilfsfunktionen ────────────────────────────────────────────────────────────

def load_config() -> dict:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return deepcopy(DEFAULT_CONFIG)

def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def pil_to_pixmap(img: Image.Image) -> QPixmap:
    img = img.convert("RGBA")
    data = img.tobytes("raw", "RGBA")
    qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg)

def load_icon_pixmap(path: str, size: int = 64) -> QPixmap | None:
    if not path:
        return None
    p = Path(os.path.expanduser(path))
    if not p.exists():
        return None
    try:
        img = Image.open(p).convert("RGBA").resize((size, size), Image.LANCZOS)
        return pil_to_pixmap(img)
    except Exception:
        return None

def make_deck_image(deck, icon_path: str, label: str,
                    bg=(30, 30, 30), fg=(255, 255, 255), flash=False) -> bytes:
    img = PILHelper.create_key_image(deck, background=bg)
    w, h = img.size
    if icon_path:
        ip = Path(os.path.expanduser(icon_path))
        if ip.exists():
            try:
                icon = Image.open(ip).convert("RGBA").resize((w, h), Image.LANCZOS)
                if flash:
                    enhancer = ImageEnhance.Brightness(icon)
                    icon = enhancer.enhance(2.5)
                img.paste(icon, (0, 0), icon)
            except Exception:
                pass
    elif flash:
        img = Image.new("RGB", (w, h), (180, 180, 220))
    if label:
        draw = ImageDraw.Draw(img)
        try:
            font = PilFont.truetype(FONT_PATH, 13)
        except Exception:
            font = PilFont.load_default()
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        tx = (w - tw) // 2
        ty = h - 18
        draw.text((tx + 1, ty + 1), label, fill=(0, 0, 0), font=font)
        draw.text((tx, ty), label, fill=fg, font=font)
    return PILHelper.to_native_key_format(deck, img)


# ── Deck-Controller-Thread ─────────────────────────────────────────────────────

class DeckThread(QThread):
    key_pressed  = Signal(int)
    connected    = Signal(bool)
    deck_shape   = Signal(int, int)   # cols, rows

    def __init__(self, config_ref: list):
        super().__init__()
        self._cfg        = config_ref   # mutable list[dict] so GUI can update it
        self._running    = True
        self._deck       = None
        self._page       = 0
        self._toggle     = {}           # (page, key) -> bool
        self._press_time = {}
        self._lock       = __import__("threading").Lock()

    def stop(self):
        self._running = False
        if self._deck:
            try: self._deck.close()
            except: pass

    def run(self):
        while self._running:
            self._try_connect()
            time.sleep(3)

    def _try_connect(self):
        try:
            devices = DM.DeviceManager().enumerate()
            if not devices:
                return
            self._deck = devices[0]
            self._deck.open()
            self._deck.reset()
            cfg = self._cfg[0]
            self._deck.set_brightness(cfg.get("brightness", 80))
            self._deck.set_key_callback(self._callback)
            cols = getattr(self._deck, "KEY_COLS", 5)
            rows = getattr(self._deck, "KEY_ROWS", 3)
            self.deck_shape.emit(cols, rows)
            self.connected.emit(True)
            log.info(f"Deck verbunden: {self._deck.deck_type()}, {self._deck.key_count()} Tasten")
            self.refresh_all()
            while self._running and self._deck.connected():
                time.sleep(0.1)
        except TransportError:
            pass
        except Exception as e:
            log.warning(f"Deck-Fehler: {e}")
        finally:
            if self._deck:
                try: self._deck.close()
                except: pass
                self._deck = None
            self.connected.emit(False)

    def _callback(self, deck, key, pressed):
        if pressed:
            with self._lock:
                self._press_time[key] = time.time()
            self._fire(key)
            self.key_pressed.emit(key)

    def _fire(self, key):
        cfg    = self._cfg[0]
        page   = cfg.get("pages", [{}])[self._page]
        kc     = page.get("keys", {}).get(str(key), {})
        action = kc.get("single_press")
        if not action:
            return
        fn_id = action.get("_fn_id", "")
        fn    = FN_BY_ID.get(fn_id)
        is_toggle = fn[4] if fn else False

        if is_toggle:
            state = self._toggle.get((self._page, key), False)
            self._toggle[(self._page, key)] = not state
            self._render_key(key)
        else:
            self._flash_key(key)

        self._run_action(action, key)

    def _run_action(self, action, key):
        if not action:
            return
        t = action.get("type")
        if t == "command":
            cmd = action.get("cmd", "")
            if cmd:
                subprocess.Popen(cmd, shell=True)
        elif t == "spotify_dbus":
            self._spotify_dbus(action.get("command", ""))
        elif t == "song_info_clipboard":
            self._song_info()
        elif t == "page":
            target = action.get("target", 0)
            self._page = target
            self.refresh_all()

    def _spotify_dbus(self, cmd):
        base = ["dbus-send", "--print-reply", "--dest=org.mpris.MediaPlayer2.spotify",
                "/org/mpris/MediaPlayer2"]
        try:
            if cmd == "play_pause":
                subprocess.run(base + ["org.mpris.MediaPlayer2.Player.PlayPause"])
            elif cmd == "next":
                subprocess.run(base + ["org.mpris.MediaPlayer2.Player.Next"])
            elif cmd == "previous":
                subprocess.run(base + ["org.mpris.MediaPlayer2.Player.Previous"])
            elif cmd == "open_spotify":
                subprocess.Popen(["spotify"])
        except Exception as e:
            log.warning(f"DBus {cmd}: {e}")

    def _song_info(self):
        try:
            import re
            r = subprocess.run(
                ["dbus-send", "--print-reply", "--dest=org.mpris.MediaPlayer2.spotify",
                 "/org/mpris/MediaPlayer2",
                 "org.freedesktop.DBus.Properties.Get",
                 "string:org.mpris.MediaPlayer2.Player", "string:Metadata"],
                capture_output=True, text=True, timeout=3
            )
            out = r.stdout
            t = re.search(r'"xesam:title".*?\n\s+variant\s+string\s+"([^"]+)"', out)
            a = re.search(r'"xesam:artist".*?\n.*?\n\s+"([^"]+)"', out)
            text = f"{a.group(1)} – {t.group(1)}" if t and a else "Kein Song"
            p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
            p.communicate(text.encode())
        except Exception as e:
            log.warning(f"Song-Info: {e}")

    def refresh_all(self):
        if not self._deck:
            return
        cfg  = self._cfg[0]
        page = cfg.get("pages", [{}])[self._page] if self._page < len(cfg.get("pages", [])) else {}
        for i in range(self._deck.key_count()):
            self._render_key(i, page)

    def _render_key(self, key, page=None):
        if not self._deck:
            return
        cfg    = self._cfg[0]
        if page is None:
            pages = cfg.get("pages", [{}])
            page  = pages[self._page] if self._page < len(pages) else {}
        kc     = page.get("keys", {}).get(str(key), {})
        active = self._toggle.get((self._page, key), False)
        icon   = kc.get("icon_active" if active else "icon", "")
        label  = kc.get("label", "")
        try:
            self._deck.set_key_image(key, make_deck_image(self._deck, icon, label))
        except Exception:
            pass

    def _flash_key(self, key):
        if not self._deck:
            return
        cfg   = self._cfg[0]
        pages = cfg.get("pages", [{}])
        page  = pages[self._page] if self._page < len(pages) else {}
        kc    = page.get("keys", {}).get(str(key), {})
        icon  = kc.get("icon", "")
        label = kc.get("label", "")
        try:
            self._deck.set_key_image(key, make_deck_image(self._deck, icon, label, flash=True))
        except Exception:
            pass
        # Revert nach 250ms
        t = __import__("threading").Timer(0.25, lambda: self._render_key(key))
        t.daemon = True
        t.start()

    def set_page(self, idx: int):
        self._page = idx
        self.refresh_all()

    def update_config(self, cfg: dict):
        self._cfg[0] = cfg
        if self._deck:
            self._deck.set_brightness(cfg.get("brightness", 80))
        self.refresh_all()


# ── Taste-Widget (im GUI-Grid) ─────────────────────────────────────────────────

class KeyButton(QPushButton):
    BASE_STYLE   = "QPushButton{background:#1e1e2e;border:2px solid #313244;border-radius:8px;color:#cdd6f4;font-size:10px;}"
    ACTIVE_STYLE = "QPushButton{background:#313244;border:2px solid #89b4fa;border-radius:8px;color:#89b4fa;font-size:10px;}"
    FLASH_STYLE  = "QPushButton{background:#45475a;border:2px solid #cba6f7;border-radius:8px;}"

    def __init__(self, idx: int, parent=None):
        super().__init__(parent)
        self.idx = idx
        self.setFixedSize(72, 72)
        self.setIconSize(QSize(56, 56))
        self.setStyleSheet(self.BASE_STYLE)

    def set_selected(self, selected: bool):
        self.setStyleSheet(self.ACTIVE_STYLE if selected else self.BASE_STYLE)

    def flash(self):
        self.setStyleSheet(self.FLASH_STYLE)
        QTimer.singleShot(200, lambda: self.setStyleSheet(self.BASE_STYLE))

    def update_display(self, icon_path: str, label: str):
        px = load_icon_pixmap(icon_path, 56)
        if px:
            self.setIcon(QIcon(px))
            self.setText("")
        else:
            self.setIcon(QIcon())
            self.setText(label or str(self.idx))


# ── Konfigurations-Panel für eine Taste ───────────────────────────────────────

class KeyConfigPanel(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._key_idx   = None
        self._page_idx  = None
        self._cfg       = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._title = QLabel("Taste auswählen")
        self._title.setStyleSheet("font-weight:bold;font-size:13px;color:#cdd6f4;")
        layout.addWidget(self._title)

        # Label
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Beschriftung:"))
        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("z.B. Play")
        self._label_edit.textChanged.connect(self._on_change)
        row1.addWidget(self._label_edit)
        layout.addLayout(row1)

        # Funktion
        layout.addWidget(QLabel("Funktion (Drücken):"))
        self._fn_combo = QComboBox()
        self._fn_combo.setMinimumWidth(240)
        cur_cat = None
        for cat, fid, name, _, _ in FUNCTION_LIBRARY:
            if cat != cur_cat:
                self._fn_combo.insertSeparator(self._fn_combo.count())
                self._fn_combo.addItem(f"── {cat} ──")
                item = self._fn_combo.model().item(self._fn_combo.count() - 1)
                item.setEnabled(False)
                cur_cat = cat
            self._fn_combo.addItem(name, fid)
        self._fn_combo.currentIndexChanged.connect(self._on_fn_change)
        layout.addWidget(self._fn_combo)

        # Extra-Feld für anpassbare Befehle
        self._extra_label = QLabel("Befehl / URL / App:")
        self._extra_edit  = QLineEdit()
        self._extra_edit.setPlaceholderText("")
        self._extra_edit.textChanged.connect(self._on_change)
        layout.addWidget(self._extra_label)
        layout.addWidget(self._extra_edit)

        # Icons
        icon_group = QGroupBox("Icons")
        icon_group.setStyleSheet("QGroupBox{color:#cdd6f4;border:1px solid #313244;border-radius:6px;margin-top:6px;padding-top:6px;}")
        ig_layout  = QGridLayout(icon_group)

        ig_layout.addWidget(QLabel("Normal:"), 0, 0)
        self._icon_normal_preview = QLabel()
        self._icon_normal_preview.setFixedSize(40, 40)
        self._icon_normal_preview.setStyleSheet("background:#313244;border-radius:4px;")
        ig_layout.addWidget(self._icon_normal_preview, 0, 1)
        btn_normal = QPushButton("Wählen…")
        btn_normal.clicked.connect(lambda: self._pick_icon("normal"))
        ig_layout.addWidget(btn_normal, 0, 2)
        btn_clear_n = QPushButton("✕")
        btn_clear_n.setFixedWidth(28)
        btn_clear_n.clicked.connect(lambda: self._clear_icon("normal"))
        ig_layout.addWidget(btn_clear_n, 0, 3)

        ig_layout.addWidget(QLabel("Aktiv:"), 1, 0)
        self._icon_active_preview = QLabel()
        self._icon_active_preview.setFixedSize(40, 40)
        self._icon_active_preview.setStyleSheet("background:#313244;border-radius:4px;")
        ig_layout.addWidget(self._icon_active_preview, 1, 1)
        btn_active = QPushButton("Wählen…")
        btn_active.clicked.connect(lambda: self._pick_icon("active"))
        ig_layout.addWidget(btn_active, 1, 2)
        btn_clear_a = QPushButton("✕")
        btn_clear_a.setFixedWidth(28)
        btn_clear_a.clicked.connect(lambda: self._clear_icon("active"))
        ig_layout.addWidget(btn_clear_a, 1, 3)

        layout.addWidget(icon_group)
        layout.addStretch()

        # Speichern
        self._save_btn = QPushButton("Speichern")
        self._save_btn.setStyleSheet("QPushButton{background:#89b4fa;color:#1e1e2e;font-weight:bold;border-radius:6px;padding:6px;}")
        self._save_btn.clicked.connect(self._save)
        layout.addWidget(self._save_btn)

        self.setEnabled(False)

    def load_key(self, page_idx: int, key_idx: int, cfg: dict):
        self._page_idx = page_idx
        self._key_idx  = key_idx
        self._cfg      = cfg
        self.setEnabled(True)
        self._title.setText(f"Taste {key_idx} konfigurieren")

        pages  = cfg.get("pages", [{}])
        page   = pages[page_idx] if page_idx < len(pages) else {}
        kc     = page.get("keys", {}).get(str(key_idx), {})
        action = kc.get("single_press") or {}
        fn_id  = action.get("_fn_id", "none")

        self._label_edit.blockSignals(True)
        self._label_edit.setText(kc.get("label", ""))
        self._label_edit.blockSignals(False)

        # Funktion setzen
        for i in range(self._fn_combo.count()):
            if self._fn_combo.itemData(i) == fn_id:
                self._fn_combo.blockSignals(True)
                self._fn_combo.setCurrentIndex(i)
                self._fn_combo.blockSignals(False)
                break

        # Extra-Befehl
        self._extra_edit.blockSignals(True)
        self._extra_edit.setText(action.get("cmd", action.get("target", "")))
        self._extra_edit.blockSignals(False)
        self._update_extra_visibility(fn_id)

        # Icons
        self._set_icon_preview("normal", kc.get("icon", ""))
        self._set_icon_preview("active", kc.get("icon_active", ""))

    def _on_fn_change(self):
        fn_id = self._fn_combo.currentData()
        self._update_extra_visibility(fn_id)
        self._on_change()

    def _update_extra_visibility(self, fn_id: str):
        show = fn_id in ("app_launch", "open_url", "open_folder", "custom_cmd", "page_switch")
        self._extra_label.setVisible(show)
        self._extra_edit.setVisible(show)
        if fn_id == "page_switch":
            self._extra_label.setText("Seiten-Nummer (0 = erste):")
            self._extra_edit.setPlaceholderText("0")
        elif fn_id == "open_url":
            self._extra_label.setText("URL:")
            self._extra_edit.setPlaceholderText("https://...")
        elif fn_id in ("app_launch", "custom_cmd"):
            self._extra_label.setText("Befehl:")
            self._extra_edit.setPlaceholderText("z.B. firefox")
        elif fn_id == "open_folder":
            self._extra_label.setText("Pfad:")
            self._extra_edit.setPlaceholderText("~/Downloads")

    def _pick_icon(self, which: str):
        start = str(ICONS_DIR) if ICONS_DIR.exists() else str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, "Icon wählen", start, "Bilder (*.png *.jpg *.jpeg *.svg *.webp)"
        )
        if path:
            self._set_icon_preview(which, path)
            self._on_change()

    def _clear_icon(self, which: str):
        self._set_icon_preview(which, "")
        self._on_change()

    def _set_icon_preview(self, which: str, path: str):
        lbl = self._icon_normal_preview if which == "normal" else self._icon_active_preview
        setattr(self, f"_icon_{which}_path", path)
        px = load_icon_pixmap(path, 38)
        if px:
            lbl.setPixmap(px.scaled(38, 38, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            lbl.setPixmap(QPixmap())

    def _on_change(self):
        pass  # live-save könnte hier hin

    def _save(self):
        if self._key_idx is None:
            return
        fn_id   = self._fn_combo.currentData() or "none"
        fn      = FN_BY_ID.get(fn_id)
        action  = deepcopy(fn[3]) if fn and fn[3] else None

        if action:
            action["_fn_id"] = fn_id
            extra = self._extra_edit.text().strip()
            if fn_id == "page_switch":
                try:    action["target"] = int(extra)
                except: action["target"] = 0
            elif "cmd" in action and extra:
                action["cmd"] = extra

        pages = self._cfg.setdefault("pages", [{}])
        while len(pages) <= self._page_idx:
            pages.append({"name": f"Seite {len(pages)}", "keys": {}})
        keys = pages[self._page_idx].setdefault("keys", {})
        kc   = keys.setdefault(str(self._key_idx), {})

        kc["label"] = self._label_edit.text().strip()
        if action:
            kc["single_press"] = action
        elif "single_press" in kc:
            del kc["single_press"]

        icon_n = getattr(self, "_icon_normal_path", "")
        icon_a = getattr(self, "_icon_active_path", "")
        if icon_n: kc["icon"]        = icon_n
        elif "icon" in kc: del kc["icon"]
        if icon_a: kc["icon_active"] = icon_a
        elif "icon_active" in kc: del kc["icon_active"]

        save_config(self._cfg)
        self.changed.emit()


# ── Haupt-Fenster ──────────────────────────────────────────────────────────────

class StreamDeckWindow(QMainWindow):
    def __init__(self, config_ref: list):
        super().__init__()
        self._cfg_ref  = config_ref
        self._cfg      = config_ref[0]
        self._page_idx = 0
        self._selected = None
        self._key_btns: list[KeyButton] = []
        self._cols, self._rows = 5, 3

        self.setWindowTitle("Stream Deck")
        self.setMinimumSize(720, 520)
        self._apply_dark_theme()
        self._build_ui()

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #1e1e2e; color: #cdd6f4; }
            QLabel { color: #cdd6f4; }
            QLineEdit, QComboBox, QSpinBox {
                background: #313244; color: #cdd6f4; border: 1px solid #45475a;
                border-radius: 4px; padding: 4px;
            }
            QPushButton {
                background: #313244; color: #cdd6f4; border: 1px solid #45475a;
                border-radius: 4px; padding: 4px 10px;
            }
            QPushButton:hover { background: #45475a; }
            QGroupBox { border: 1px solid #313244; border-radius:6px; margin-top:8px; color:#cdd6f4; }
            QTabWidget::pane { border: 1px solid #313244; }
            QTabBar::tab { background:#313244; color:#cdd6f4; padding:6px 14px; border-radius:4px 4px 0 0; }
            QTabBar::tab:selected { background:#45475a; }
        """)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # ── Links: Grid + Seiten-Tabs ──────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(10)

        # Status-Label
        self._status_lbl = QLabel("Suche Stream Deck…")
        self._status_lbl.setStyleSheet("color:#a6e3a1;font-size:11px;")
        left.addWidget(self._status_lbl)

        # Seiten-Tabs
        tab_row = QHBoxLayout()
        self._page_tabs = QTabWidget()
        self._page_tabs.setMaximumHeight(36)
        self._page_tabs.tabBar().tabBarClicked.connect(self._on_page_tab)
        tab_row.addWidget(QLabel("Seite:"))
        tab_row.addWidget(self._page_tabs)
        btn_add_page = QPushButton("+")
        btn_add_page.setFixedWidth(28)
        btn_add_page.setToolTip("Seite hinzufügen")
        btn_add_page.clicked.connect(self._add_page)
        tab_row.addWidget(btn_add_page)
        btn_del_page = QPushButton("−")
        btn_del_page.setFixedWidth(28)
        btn_del_page.setToolTip("Seite löschen")
        btn_del_page.clicked.connect(self._del_page)
        tab_row.addWidget(btn_del_page)
        left.addLayout(tab_row)

        # Grid-Container
        self._grid_widget = QWidget()
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setSpacing(6)
        left.addWidget(self._grid_widget)
        left.addStretch()

        # Helligkeit
        bright_row = QHBoxLayout()
        bright_row.addWidget(QLabel("Helligkeit:"))
        self._brightness_spin = QSpinBox()
        self._brightness_spin.setRange(0, 100)
        self._brightness_spin.setSuffix(" %")
        self._brightness_spin.setValue(self._cfg.get("brightness", 80))
        self._brightness_spin.valueChanged.connect(self._on_brightness)
        bright_row.addWidget(self._brightness_spin)
        bright_row.addStretch()
        left.addLayout(bright_row)

        # Deinstallieren
        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setStyleSheet("color:#313244;")
        left.addWidget(sep)
        uninstall_btn = QPushButton("App deinstallieren…")
        uninstall_btn.setStyleSheet("QPushButton{color:#f38ba8;border:1px solid #f38ba8;border-radius:4px;padding:4px;}")
        uninstall_btn.clicked.connect(self._uninstall_dialog)
        left.addWidget(uninstall_btn)

        root.addLayout(left)

        # ── Rechts: Konfig-Panel ──────────────────────────────────────────
        self._key_panel = KeyConfigPanel()
        self._key_panel.changed.connect(self._on_config_changed)
        self._key_panel.setFixedWidth(300)
        root.addWidget(self._key_panel)

        self._rebuild_grid(self._cols, self._rows)
        self._rebuild_page_tabs()

    def _rebuild_grid(self, cols: int, rows: int):
        self._cols, self._rows = cols, rows
        # Altes Grid leeren
        for btn in self._key_btns:
            self._grid_layout.removeWidget(btn)
            btn.deleteLater()
        self._key_btns.clear()

        for r in range(rows):
            for c in range(cols):
                idx = r * cols + c
                btn = KeyButton(idx)
                btn.clicked.connect(lambda _, i=idx: self._select_key(i))
                self._grid_layout.addWidget(btn, r, c)
                self._key_btns.append(btn)
        self._refresh_grid()

    def _refresh_grid(self):
        pages = self._cfg.get("pages", [{}])
        page  = pages[self._page_idx] if self._page_idx < len(pages) else {}
        for btn in self._key_btns:
            kc = page.get("keys", {}).get(str(btn.idx), {})
            btn.update_display(kc.get("icon", ""), kc.get("label", ""))
            btn.set_selected(btn.idx == self._selected)

    def _select_key(self, idx: int):
        self._selected = idx
        for btn in self._key_btns:
            btn.set_selected(btn.idx == idx)
        self._key_panel.load_key(self._page_idx, idx, self._cfg)

    def _on_page_tab(self, idx: int):
        self._page_idx = idx
        self._selected = None
        self._key_panel.setEnabled(False)
        self._refresh_grid()

    def _rebuild_page_tabs(self):
        self._page_tabs.blockSignals(True)
        while self._page_tabs.count():
            self._page_tabs.removeTab(0)
        for i, p in enumerate(self._cfg.get("pages", [{}])):
            self._page_tabs.addTab(QWidget(), p.get("name", f"Seite {i}"))
        self._page_tabs.blockSignals(False)

    def _add_page(self):
        pages = self._cfg.setdefault("pages", [])
        pages.append({"name": f"Seite {len(pages)}", "keys": {}})
        save_config(self._cfg)
        self._rebuild_page_tabs()

    def _del_page(self):
        pages = self._cfg.get("pages", [])
        if len(pages) <= 1:
            QMessageBox.information(self, "Seite löschen", "Mindestens eine Seite muss bleiben.")
            return
        pages.pop(self._page_idx)
        self._page_idx = max(0, self._page_idx - 1)
        save_config(self._cfg)
        self._rebuild_page_tabs()
        self._refresh_grid()

    def _on_brightness(self, val: int):
        self._cfg["brightness"] = val
        save_config(self._cfg)
        self._cfg_ref[0] = self._cfg

    def _on_config_changed(self):
        self._cfg = load_config()
        self._cfg_ref[0] = self._cfg
        self._refresh_grid()

    # ── Signale vom Deck-Thread ───────────────────────────────────────────
    def on_deck_connected(self, connected: bool):
        if connected:
            self._status_lbl.setText("Stream Deck verbunden")
            self._status_lbl.setStyleSheet("color:#a6e3a1;font-size:11px;")
        else:
            self._status_lbl.setText("Stream Deck nicht gefunden")
            self._status_lbl.setStyleSheet("color:#f38ba8;font-size:11px;")

    def on_deck_shape(self, cols: int, rows: int):
        if cols != self._cols or rows != self._rows:
            self._rebuild_grid(cols, rows)

    def on_key_pressed(self, key: int):
        if key < len(self._key_btns):
            self._key_btns[key].flash()

    # ── Deinstallation ─────────────────────────────────────────────────────
    def _uninstall_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("App deinstallieren")
        dlg.setMinimumWidth(380)
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel("<b>Stream Deck wirklich deinstallieren?</b>"))
        layout.addWidget(QLabel("Was soll gelöscht werden?"))

        chk_data = QCheckBox("Konfiguration und Icons löschen (~/.config/streamdeck)")
        chk_log  = QCheckBox("Log-Datei löschen (~/.streamdeck.log)")
        chk_venv = QCheckBox("Python-Umgebung löschen (~/.venv/streamdeck)")
        chk_data.setChecked(False)
        chk_log.setChecked(True)
        chk_venv.setChecked(True)
        layout.addWidget(chk_data)
        layout.addWidget(chk_log)
        layout.addWidget(chk_venv)

        note = QLabel(
            "<small style='color:#a6adc8;'>Die udev-Regel unter /etc/udev/rules.d/ "
            "muss manuell mit sudo gelöscht werden.</small>"
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Deinstallieren")
        btns.button(QDialogButtonBox.Ok).setStyleSheet("background:#f38ba8;color:#1e1e2e;font-weight:bold;")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)

        if dlg.exec() != QDialog.Accepted:
            return

        if chk_data.isChecked():
            shutil.rmtree(Path.home() / ".config" / "streamdeck", ignore_errors=True)
        if chk_log.isChecked():
            LOG_PATH.unlink(missing_ok=True)
        if chk_venv.isChecked():
            shutil.rmtree(Path.home() / ".venv" / "streamdeck", ignore_errors=True)

        desktop = Path.home() / ".local" / "share" / "applications" / "streamdeck.desktop"
        desktop.unlink(missing_ok=True)

        QMessageBox.information(
            self, "Deinstalliert",
            "App wurde entfernt.\n\n"
            "udev-Regel manuell löschen:\n"
            "sudo rm /etc/udev/rules.d/50-elgato-streamdeck.rules"
        )
        QApplication.quit()

    def closeEvent(self, event):
        # Fenster verstecken statt schließen – Daemon läuft weiter
        event.ignore()
        self.hide()


# ── Single-Instance & Einstiegspunkt ──────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Stream Deck")
    app.setQuitOnLastWindowClosed(False)

    # Einzelne Instanz sicherstellen
    server = QLocalServer()
    QLocalServer.removeServer(INSTANCE_KEY)

    if not server.listen(INSTANCE_KEY):
        # Schon läuft – vorhandene Instanz fokussieren
        sock = QLocalSocket()
        sock.connectToServer(INSTANCE_KEY)
        if sock.waitForConnected(500):
            sock.write(b"show")
            sock.flush()
            sock.disconnectFromServer()
        return

    cfg_ref = [load_config()]

    deck_thread = DeckThread(cfg_ref)

    window = StreamDeckWindow(cfg_ref)

    # Deck-Thread → GUI-Signale verbinden
    deck_thread.connected.connect(window.on_deck_connected)
    deck_thread.deck_shape.connect(window.on_deck_shape)
    deck_thread.key_pressed.connect(window.on_key_pressed)

    # Bei neuer Verbindung (zweiter Klick im App-Menü) → Fenster zeigen
    def _on_new_connection():
        conn = server.nextPendingConnection()
        if conn:
            conn.waitForReadyRead(300)
        window.show()
        window.raise_()
        window.activateWindow()
    server.newConnection.connect(_on_new_connection)

    deck_thread.start()
    window.show()

    ret = app.exec()
    deck_thread.stop()
    deck_thread.wait(2000)
    sys.exit(ret)


if __name__ == "__main__":
    main()
