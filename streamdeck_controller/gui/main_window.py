"""Hauptfenster: Tasten-Grid + Konfiguration links, Auto-Hide-Funktionspalette rechts,
Einstellungen als eigene Seite (Zahnrad / Zurück)."""

import subprocess
import sys
import threading

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMessageBox,
    QPushButton, QSlider, QStackedWidget, QTabBar, QVBoxLayout, QWidget,
)

from .. import __version__, autostart
from ..actions import get_spec
from ..config import get_key_config, load_config, save_config, set_key_config
from ..deck.manager import enumerate_decks
from ..ipc import ipc_request
from . import style
from .key_panel import KeyConfigPanel
from .settings_page import SettingsPage
from .widgets import ActionPalette, KeyGrid

DEFAULT_COLS, DEFAULT_ROWS = 3, 2  # Stream Deck Mini
RESCAN = "__rescan__"
PALETTE_WIDTH = 280
WIDE_THRESHOLD = 1000    # ab dieser Breite ist die Palette fest angedockt
COMPACT_THRESHOLD = 820  # darunter: kompakte Topbar + kleinere Kacheln
COMPACT_HEIGHT = 800

_SMALL = "padding:2px;font-weight:bold;"
_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class _HoverStrip(QWidget):
    """Schmaler Streifen am rechten Rand — beim Hovern erscheint die Palette."""

    def __init__(self, on_enter, parent=None):
        super().__init__(parent)
        self._on_enter = on_enter
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(18)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Funktionen einblenden")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        arrow = QLabel("◂")
        arrow.setAlignment(Qt.AlignCenter)
        arrow.setStyleSheet(f"color:{style.SUBTEXT};font-size:14px;")
        layout.addWidget(arrow)
        self.setStyleSheet(
            f"_HoverStrip{{background:{style.CARD};border-radius:8px;}}")

    def enterEvent(self, event):
        self._on_enter()

    def mousePressEvent(self, event):
        self._on_enter()


class _PaletteOverlay(QWidget):
    """Schwebende Funktionspalette; verschwindet, wenn der Cursor sie verlässt.

    Die ActionPalette selbst wird von außen hineingesetzt (host) — sie wandert
    je nach Fensterbreite zwischen Overlay und fest angedocktem Bereich.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(PALETTE_WIDTH)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(10, 10, 10, 10)
        self.setStyleSheet(
            f"_PaletteOverlay{{background:{style.BG};"
            f"border:1px solid {style.SURFACE_HI};border-radius:12px;}}")
        self.hide()

    def host(self, widget: QWidget):
        self._layout.addWidget(widget)

    def leaveEvent(self, event):
        self.hide()


class MainWindow(QMainWindow):
    _devices_ready = Signal(list, bool)  # [(label, serial)], dropdown offen halten

    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.page_idx = 0
        self.selected_key: int | None = None
        self._daemon_was_connected = None
        self._syncing_page = False
        self._wide_mode: bool | None = None
        self._compact_mode: bool | None = None
        self._scanning = False
        self._spinner_phase = 0

        self.setWindowTitle(f"Stream Deck Controller {__version__}")
        self.setMinimumSize(660, 700)
        self._build_ui()
        self._refresh_all()

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._poll_status)
        self._status_timer.start(1000)
        self._poll_status()

    # ── Aufbau ────────────────────────────────────────────────────────
    def _build_ui(self):
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Seite 0: Hauptansicht
        self._main_page = QWidget()
        self._stack.addWidget(self._main_page)
        outer = QHBoxLayout(self._main_page)
        outer.setContentsMargins(14, 10, 6, 14)
        outer.setSpacing(8)

        left = QVBoxLayout()
        left.setSpacing(10)

        # ── Kopfzeile ────────────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(8)

        self._status_dot = QLabel()
        self._status_dot.setFixedSize(14, 14)
        self._set_dot(style.RED, "Daemon läuft nicht")
        top.addWidget(self._status_dot)

        self._start_btn = QPushButton("Daemon starten")
        self._start_btn.clicked.connect(self._start_daemon)
        self._start_btn.hide()
        top.addWidget(self._start_btn)
        top.addStretch()

        self._device_label = QLabel("Gerät")
        top.addWidget(self._device_label)
        self._device_combo = QComboBox()
        self._device_combo.setMinimumWidth(170)
        self._device_combo.activated.connect(self._on_device_selected)
        top.addWidget(self._device_combo)

        settings_btn = QPushButton("⚙")
        settings_btn.setFixedSize(30, 30)
        settings_btn.setStyleSheet("padding:0;font-size:16px;")
        settings_btn.setToolTip("Einstellungen")
        settings_btn.clicked.connect(self._open_settings)
        top.addWidget(settings_btn)
        left.addLayout(top)

        # ── Seiten ───────────────────────────────────────────────────
        page_row = QHBoxLayout()
        self._page_bar = QTabBar()
        self._page_bar.setMovable(False)
        self._page_bar.currentChanged.connect(self._on_page_changed)
        self._page_bar.tabBarDoubleClicked.connect(self._rename_page)
        page_row.addWidget(self._page_bar)
        for text, tip, handler in (("+", "Seite hinzufügen", self._add_page),
                                   ("−", "Seite löschen", self._del_page)):
            btn = QPushButton(text)
            btn.setFixedWidth(28)
            btn.setStyleSheet(_SMALL)
            btn.setToolTip(tip)
            btn.clicked.connect(handler)
            page_row.addWidget(btn)
        page_row.addStretch()
        left.addLayout(page_row)

        # ── Grid ─────────────────────────────────────────────────────
        self.grid = KeyGrid()
        self.grid.rebuild(DEFAULT_COLS, DEFAULT_ROWS)
        self.grid.action_dropped.connect(self._on_action_dropped)
        self.grid.key_moved.connect(self._on_key_moved)
        self.grid.key_selected.connect(self._on_key_selected)
        self.grid.key_clear.connect(self._on_key_clear)
        grid_wrap = QHBoxLayout()
        grid_wrap.addStretch()
        grid_wrap.addWidget(self.grid)
        grid_wrap.addStretch()
        left.addLayout(grid_wrap)

        bright_row = QHBoxLayout()
        bright_row.addWidget(QLabel("Helligkeit:"))
        self._bright = QSlider(Qt.Horizontal)
        self._bright.setRange(0, 100)
        self._bright.setValue(self.cfg.get("brightness", 80))
        self._bright.sliderReleased.connect(self._on_brightness)
        self._bright.setMaximumWidth(220)
        bright_row.addWidget(self._bright)
        self._bright_lbl = QLabel(f"{self._bright.value()} %")
        self._bright.valueChanged.connect(lambda v: self._bright_lbl.setText(f"{v} %"))
        bright_row.addWidget(self._bright_lbl)
        bright_row.addStretch()
        left.addLayout(bright_row)

        # ── Tasten-Konfiguration (ohne Scrollen erreichbar) ──────────
        self.panel = KeyConfigPanel(
            pages_provider=lambda: [p.get("name", "Seite")
                                    for p in self.cfg.get("pages", [])])
        self.panel.changed.connect(self._on_panel_changed)
        left.addWidget(self.panel, stretch=1)

        outer.addLayout(left, stretch=1)

        # ── Funktionspalette: breit = fest angedockt, schmal = Auto-Hide ─
        self.palette = ActionPalette()

        self._strip = _HoverStrip(self._show_palette)
        outer.addWidget(self._strip)

        self._dock = QWidget()
        self._dock.setObjectName("paletteDock")
        self._dock.setAttribute(Qt.WA_StyledBackground, True)
        self._dock.setFixedWidth(PALETTE_WIDTH)
        self._dock.setStyleSheet(
            f"#paletteDock{{background:{style.BG};"
            f"border:1px solid {style.SURFACE_HI};border-radius:12px;}}")
        self._dock_layout = QVBoxLayout(self._dock)
        self._dock_layout.setContentsMargins(10, 10, 10, 10)
        self._dock.hide()
        outer.addWidget(self._dock)

        self._palette_overlay = _PaletteOverlay(self._main_page)
        self._palette_overlay.host(self.palette)

        # Seite 1: Einstellungen
        self._settings = SettingsPage()
        self._settings.back_requested.connect(self._close_settings)
        self._stack.addWidget(self._settings)

        self._spinner_timer = QTimer(self)
        self._spinner_timer.timeout.connect(self._spin_tick)
        self._devices_ready.connect(self._on_devices_ready)
        self._refresh_devices()
        self._apply_layout_mode()

    # ── Palette / Responsive ──────────────────────────────────────────
    def _show_palette(self):
        self._place_palette()
        self._palette_overlay.show()
        self._palette_overlay.raise_()

    def _place_palette(self):
        host = self._main_page
        self._palette_overlay.setGeometry(
            host.width() - PALETTE_WIDTH - 4, 6,
            PALETTE_WIDTH, host.height() - 12)

    def _apply_layout_mode(self):
        # Breites Fenster: Palette fest angedockt, alles dauerhaft sichtbar.
        wide = self.width() >= WIDE_THRESHOLD
        if wide != self._wide_mode:
            self._wide_mode = wide
            if wide:
                self._palette_overlay.hide()
                self._dock_layout.addWidget(self.palette)
                self._strip.hide()
                self._dock.show()
            else:
                self._dock.hide()
                self._palette_overlay.host(self.palette)
                self._strip.show()

        # Minimalbreite: Topbar entschärfen (Label weg, Combo nur als Pfeil)
        # und Grid-Kacheln verkleinern, damit nichts kollidiert.
        compact = (self.width() < COMPACT_THRESHOLD
                   or self.height() < COMPACT_HEIGHT)
        if compact != self._compact_mode:
            self._compact_mode = compact
            self._device_label.setVisible(not compact)
            if compact:
                self._device_combo.setMinimumWidth(0)
                self._device_combo.setMaximumWidth(64)
            else:
                self._device_combo.setMinimumWidth(170)
                self._device_combo.setMaximumWidth(16777215)
            self._device_combo.setToolTip(
                self._device_combo.currentText() if compact else "")
            self.grid.set_compact(compact)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._palette_overlay.isVisible():
            self._place_palette()
        self._apply_layout_mode()

    # ── Einstellungen ─────────────────────────────────────────────────
    def _open_settings(self):
        self._settings.reload()
        self._stack.setCurrentIndex(1)

    def _close_settings(self):
        self.cfg = load_config()
        self._stack.setCurrentIndex(0)
        self._refresh_all()

    # ── Status / Sync ─────────────────────────────────────────────────
    def _set_dot(self, color: str, tooltip: str):
        self._status_dot.setStyleSheet(
            f"background:{color};border-radius:7px;")
        self._status_dot.setToolTip(tooltip)

    def _poll_status(self):
        status = ipc_request({"cmd": "status"}, timeout=1.0)
        if not status:
            self._set_dot(style.RED, "Daemon läuft nicht")
            self._start_btn.show()
            self._daemon_was_connected = None
            return
        self._start_btn.hide()
        device = status.get("device") or {}
        if status.get("connected"):
            cols, rows = device.get("cols") or DEFAULT_COLS, device.get("rows") or DEFAULT_ROWS
            if (cols, rows) != (self.grid.cols, self.grid.rows):
                self.grid.rebuild(cols, rows)
                self._refresh_grid()
            self._set_dot(style.GREEN,
                          f"Verbunden: {device.get('type', '?')} ({device.get('keys', '?')} Tasten)")
        else:
            self._set_dot(style.YELLOW, "Daemon läuft — kein Deck gefunden (USB prüfen)")
        if self._daemon_was_connected != status.get("connected"):
            self._daemon_was_connected = status.get("connected")

        # Seiten-Sync: Deck → UI
        daemon_page = status.get("page")
        if (daemon_page is not None and daemon_page != self.page_idx
                and daemon_page < self._page_bar.count()):
            self._syncing_page = True
            try:
                self._page_bar.setCurrentIndex(daemon_page)
            finally:
                self._syncing_page = False

    def _start_daemon(self):
        if autostart.is_installed():
            autostart.start()
        else:
            subprocess.Popen([sys.executable, "-m", "streamdeck_controller", "run"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        QTimer.singleShot(1500, self._poll_status)

    # ── Geräte ────────────────────────────────────────────────────────
    def _refresh_devices(self, keep_open: bool = False):
        """Geräteliste asynchron neu aufbauen (USB-Scan blockiert sonst die UI)."""
        if self._scanning:
            return
        self._scanning = True
        self._device_combo.clear()
        self._device_combo.addItem("⠋ Suche Geräte…")
        self._spinner_phase = 0
        self._spinner_timer.start(120)
        if keep_open:
            QTimer.singleShot(0, self._device_combo.showPopup)
        threading.Thread(target=self._scan_devices, args=(keep_open,),
                         daemon=True, name="device-scan").start()

    def _scan_devices(self, keep_open: bool):
        entries = []
        try:
            status = ipc_request({"cmd": "status"}, timeout=1.0) or {}
            connected_serial = (status.get("device") or {}).get("serial")
            for deck in enumerate_decks():
                try:
                    deck_type = deck.deck_type()
                except Exception:
                    deck_type = "Stream Deck"
                serial = None
                try:
                    deck.open()
                    serial = deck.get_serial_number()
                    deck.close()
                except Exception:
                    serial = connected_serial  # vom Daemon belegt
                label = f"{deck_type}" + (f"  [{serial}]" if serial else "")
                entries.append((label, serial))
        finally:
            # Immer melden — sonst bliebe _scanning hängen und der Spinner ewig
            self._devices_ready.emit(entries, keep_open)

    def _on_devices_ready(self, entries: list, keep_open: bool):
        self._spinner_timer.stop()
        self._scanning = False
        combo = self._device_combo
        combo.clear()
        combo.addItem("Automatisch (erstes Deck)", None)
        for label, serial in entries:
            combo.addItem(label, serial)
        combo.insertSeparator(combo.count())
        combo.addItem("⟳  Geräte suchen…", RESCAN)
        wanted = self.cfg.get("device", {}).get("serial")
        idx = combo.findData(wanted)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        if self._compact_mode:
            combo.setToolTip(combo.currentText())
        if keep_open:
            combo.showPopup()  # frisch befüllte Liste direkt zeigen

    def _spin_tick(self):
        self._spinner_phase = (self._spinner_phase + 1) % len(_SPINNER)
        self._device_combo.setItemText(
            0, f"{_SPINNER[self._spinner_phase]} Suche Geräte…")

    def _on_device_selected(self, idx: int):
        if self._scanning:
            return
        data = self._device_combo.itemData(idx)
        if data == RESCAN:
            self._refresh_devices(keep_open=True)
            return
        if self._compact_mode:
            self._device_combo.setToolTip(self._device_combo.currentText())
        self.cfg.setdefault("device", {})["serial"] = data
        self._save_and_reload()

    # ── Seiten ────────────────────────────────────────────────────────
    def _rebuild_pages(self):
        self._page_bar.blockSignals(True)
        while self._page_bar.count():
            self._page_bar.removeTab(0)
        for page in self.cfg.get("pages", []):
            self._page_bar.addTab(page.get("name", "Seite"))
        self.page_idx = min(self.page_idx, max(0, self._page_bar.count() - 1))
        self._page_bar.setCurrentIndex(self.page_idx)
        self._page_bar.blockSignals(False)

    def _on_page_changed(self, idx: int):
        if idx < 0:
            return
        self.page_idx = idx
        self.selected_key = None
        self.panel.clear_selection()
        self._refresh_grid()
        if not self._syncing_page:
            ipc_request({"cmd": "page", "page": idx}, timeout=1.0)

    def _add_page(self):
        pages = self.cfg.setdefault("pages", [])
        pages.append({"name": f"Seite {len(pages) + 1}", "keys": {}})
        self._save_and_reload()
        self._rebuild_pages()
        self._page_bar.setCurrentIndex(len(pages) - 1)

    def _del_page(self):
        pages = self.cfg.get("pages", [])
        if len(pages) <= 1:
            QMessageBox.information(self, "Seite löschen", "Mindestens eine Seite muss bleiben.")
            return
        name = pages[self.page_idx].get("name", "?")
        if QMessageBox.question(self, "Seite löschen",
                                f"Seite „{name}“ wirklich löschen?") != QMessageBox.Yes:
            return
        pages.pop(self.page_idx)
        self.page_idx = max(0, self.page_idx - 1)
        self._save_and_reload()
        self._rebuild_pages()
        self._refresh_grid()

    def _rename_page(self, idx: int):
        pages = self.cfg.get("pages", [])
        if idx < 0 or idx >= len(pages):
            return
        name, ok = QInputDialog.getText(self, "Seite umbenennen", "Name:",
                                        text=pages[idx].get("name", ""))
        if ok and name.strip():
            pages[idx]["name"] = name.strip()
            self._save_and_reload()
            self._rebuild_pages()

    # ── Tasten ────────────────────────────────────────────────────────
    def _on_action_dropped(self, key_idx: int, action_id: str):
        spec = get_spec(action_id)
        if not spec:
            return
        kc = dict(get_key_config(self.cfg, self.page_idx, key_idx))
        actions = dict(kc.get("actions", {}))
        # Drop landet auf dem aktuell gewählten Trigger-Tab — aber nur, wenn
        # die fallengelassene Taste auch die im Panel angezeigte ist; sonst
        # ist "single" gemeint.
        trigger = (self.panel.current_trigger()
                   if key_idx == self.selected_key else "single")
        actions[trigger] = {"id": action_id, "params": {}}
        kc["actions"] = actions
        # Grafik/Beschriftung nur übernehmen, wenn die Taste neu belegt wird
        # oder der Haupt-Trigger gesetzt wird (double/hold lassen das Aussehen
        # der Taste unangetastet).
        if trigger == "single" or not kc.get("icon"):
            kc["label"] = spec.name if len(spec.name) <= 12 else ""
            kc["icon"] = spec.icon
            if spec.toggle:
                kc["icon_active"] = spec.icon_active
            else:
                kc.pop("icon_active", None)
        set_key_config(self.cfg, self.page_idx, key_idx, kc)
        self._save_and_reload()
        self._refresh_grid()
        self._select_key(key_idx)

    def _on_key_moved(self, src: int, dst: int):
        src_cfg = get_key_config(self.cfg, self.page_idx, src)
        dst_cfg = get_key_config(self.cfg, self.page_idx, dst)
        set_key_config(self.cfg, self.page_idx, dst, src_cfg)
        set_key_config(self.cfg, self.page_idx, src, dst_cfg)
        self._save_and_reload()
        self._refresh_grid()
        self._select_key(dst)

    def _on_key_selected(self, key_idx: int):
        self._select_key(key_idx)

    def _select_key(self, key_idx: int):
        self.selected_key = key_idx
        self._refresh_grid()
        self.panel.load_key(key_idx, get_key_config(self.cfg, self.page_idx, key_idx))

    def _on_key_clear(self, key_idx: int):
        set_key_config(self.cfg, self.page_idx, key_idx, {})
        self._save_and_reload()
        self._refresh_grid()
        if self.selected_key == key_idx:
            self.panel.load_key(key_idx, {})

    def _on_panel_changed(self):
        if self.selected_key is None:
            return
        set_key_config(self.cfg, self.page_idx, self.selected_key,
                       self.panel.current_key_cfg())
        self._save_and_reload()
        self._refresh_grid()

    # ── Sonstiges ─────────────────────────────────────────────────────
    def _on_brightness(self):
        self.cfg["brightness"] = self._bright.value()
        self._save_and_reload()

    def _save_and_reload(self):
        save_config(self.cfg)
        ipc_request({"cmd": "reload"}, timeout=1.0)

    def _refresh_grid(self):
        pages = self.cfg.get("pages", [{}])
        page = pages[self.page_idx] if self.page_idx < len(pages) else {}
        self.grid.refresh(page, self.selected_key)

    def _refresh_all(self):
        self._rebuild_pages()
        self._refresh_grid()
