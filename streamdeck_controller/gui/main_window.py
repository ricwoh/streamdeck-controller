"""Hauptfenster: Geräteauswahl, Seiten, Tasten-Grid, Funktions-Palette, Tasten-Panel."""

import subprocess
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QInputDialog, QLabel, QMainWindow, QMessageBox,
    QPushButton, QCheckBox, QScrollArea, QSlider, QTabBar, QVBoxLayout, QWidget,
)

from .. import __version__, autostart
from ..actions import get_spec
from ..config import get_key_config, load_config, save_config, set_key_config
from ..deck.manager import enumerate_decks
from ..ipc import ipc_request
from . import style
from .key_panel import KeyConfigPanel
from .spotify_dialog import SpotifyDialog
from .widgets import ActionPalette, KeyGrid

DEFAULT_COLS, DEFAULT_ROWS = 3, 2  # Stream Deck Mini


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.page_idx = 0
        self.selected_key: int | None = None
        self._daemon_was_connected = None

        self.setWindowTitle(f"Stream Deck Controller {__version__}")
        self.setMinimumSize(980, 560)
        self._build_ui()
        self._refresh_all()

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._poll_status)
        self._status_timer.start(2000)
        self._poll_status()

    # ── Aufbau ────────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 10, 14, 14)
        root.setSpacing(10)

        # Kopfzeile
        top = QHBoxLayout()
        self._status_lbl = QLabel("…")
        self._status_lbl.setStyleSheet(f"color:{style.SUBTEXT};font-size:12px;")
        top.addWidget(self._status_lbl)
        self._start_btn = QPushButton("Daemon starten")
        self._start_btn.clicked.connect(self._start_daemon)
        self._start_btn.hide()
        top.addWidget(self._start_btn)
        top.addStretch()

        top.addWidget(QLabel("Gerät:"))
        self._device_combo = QComboBox()
        self._device_combo.setMinimumWidth(220)
        self._device_combo.activated.connect(self._on_device_selected)
        top.addWidget(self._device_combo)
        refresh_btn = QPushButton("⟳")
        refresh_btn.setFixedWidth(30)
        refresh_btn.setToolTip("Geräte neu suchen")
        refresh_btn.clicked.connect(self._refresh_devices)
        top.addWidget(refresh_btn)

        spotify_btn = QPushButton("Spotify…")
        spotify_btn.clicked.connect(self._open_spotify)
        top.addWidget(spotify_btn)

        self._autostart_chk = QCheckBox("Autostart")
        self._autostart_chk.setToolTip("Daemon beim Anmelden automatisch starten (systemd)")
        self._autostart_chk.setChecked(autostart.is_installed() and autostart.is_enabled())
        self._autostart_chk.toggled.connect(self._on_autostart)
        top.addWidget(self._autostart_chk)
        root.addLayout(top)

        # Hauptbereich: Grid | Panel | Palette
        main = QHBoxLayout()
        main.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(8)

        page_row = QHBoxLayout()
        self._page_bar = QTabBar()
        self._page_bar.setMovable(False)
        self._page_bar.currentChanged.connect(self._on_page_changed)
        self._page_bar.tabBarDoubleClicked.connect(self._rename_page)
        page_row.addWidget(self._page_bar)
        add_page = QPushButton("+")
        add_page.setFixedWidth(28)
        add_page.setToolTip("Seite hinzufügen")
        add_page.clicked.connect(self._add_page)
        page_row.addWidget(add_page)
        del_page = QPushButton("−")
        del_page.setFixedWidth(28)
        del_page.setToolTip("Seite löschen")
        del_page.clicked.connect(self._del_page)
        page_row.addWidget(del_page)
        page_row.addStretch()
        left.addLayout(page_row)

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
        left.addStretch()

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
        main.addLayout(left, stretch=4)

        self.panel = KeyConfigPanel()
        self.panel.changed.connect(self._on_panel_changed)
        panel_scroll = QScrollArea()
        panel_scroll.setWidgetResizable(True)
        panel_scroll.setWidget(self.panel)
        panel_scroll.setMinimumWidth(300)
        main.addWidget(panel_scroll, stretch=3)

        self.palette = ActionPalette()
        self.palette.setMinimumWidth(230)
        main.addWidget(self.palette, stretch=3)

        root.addLayout(main)
        self._refresh_devices()

    # ── Statusabfrage beim Daemon ─────────────────────────────────────
    def _poll_status(self):
        status = ipc_request({"cmd": "status"}, timeout=1.0)
        if not status:
            self._status_lbl.setText("● Daemon läuft nicht")
            self._status_lbl.setStyleSheet(f"color:{style.RED};font-size:12px;")
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
            text = f"● Verbunden: {device.get('type', '?')} ({device.get('keys', '?')} Tasten)"
            self._status_lbl.setText(text)
            self._status_lbl.setStyleSheet(f"color:{style.GREEN};font-size:12px;")
        else:
            self._status_lbl.setText("● Daemon läuft — kein Deck gefunden (USB prüfen)")
            self._status_lbl.setStyleSheet(f"color:#f9e2af;font-size:12px;")
        if self._daemon_was_connected != status.get("connected"):
            self._daemon_was_connected = status.get("connected")

    def _start_daemon(self):
        if autostart.is_installed():
            autostart.start()
        else:
            subprocess.Popen([sys.executable, "-m", "streamdeck_controller", "run"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        QTimer.singleShot(1500, self._poll_status)

    # ── Geräte ────────────────────────────────────────────────────────
    def _refresh_devices(self):
        self._device_combo.clear()
        self._device_combo.addItem("Automatisch (erstes Deck)", None)
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
            self._device_combo.addItem(label, serial)
        wanted = self.cfg.get("device", {}).get("serial")
        idx = self._device_combo.findData(wanted)
        self._device_combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _on_device_selected(self, idx: int):
        serial = self._device_combo.itemData(idx)
        self.cfg.setdefault("device", {})["serial"] = serial
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
        actions["single"] = {"id": action_id, "params": {}}
        kc["actions"] = actions
        if not kc.get("label"):
            kc["label"] = spec.name if len(spec.name) <= 12 else ""
        if not kc.get("icon"):
            kc["icon"] = spec.icon
        if spec.toggle and not kc.get("icon_active"):
            kc["icon_active"] = spec.icon_active
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

    def _on_autostart(self, enabled: bool):
        try:
            if enabled:
                autostart.install()
            else:
                autostart.uninstall()
        except Exception as e:
            QMessageBox.warning(self, "Autostart", f"Fehler: {e}")

    def _open_spotify(self):
        dialog = SpotifyDialog(self.cfg, self)
        dialog.exec()
        self.cfg = load_config()

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
