"""Einstellungs-Seite: ersetzt die Konfigurationsansicht komplett (mit Zurück-Button).

Enthält: Autostart, Spotify-Anbindung, Bedienung (Multi-Press-Timing), Sprache.
"""

import threading

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QSpinBox, QVBoxLayout,
    QWidget,
)

from .. import autostart
from ..config import load_config, save_config
from ..ipc import ipc_request
from ..spotify import SpotifyClient, auth
from . import style

SPOTIFY_GUIDE = """\
<b>Einmalige Einrichtung:</b>
1. <a href="https://developer.spotify.com/dashboard">developer.spotify.com/dashboard</a> öffnen und einloggen<br>
2. „Create app“ — Redirect URI: <code>http://127.0.0.1:8888/callback</code>, API: Web API<br>
3. Client-ID kopieren, unten einfügen, anmelden
"""


class _LoginBridge(QObject):
    done = Signal(bool, str)


class SettingsPage(QWidget):
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = load_config()
        self._loading = False
        self._build_ui()

    # ── Aufbau ────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 14)
        root.setSpacing(10)

        head = QHBoxLayout()
        back = QPushButton("←  Zurück")
        back.clicked.connect(self.back_requested.emit)
        head.addWidget(back)
        title = QLabel("Einstellungen")
        title.setStyleSheet(f"font-weight:bold;font-size:16px;color:{style.TEXT};")
        head.addWidget(title)
        head.addStretch()
        root.addLayout(head)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(12)

        # ── Allgemein ────────────────────────────────────────────────
        general = QGroupBox("Allgemein")
        gen_form = QFormLayout(general)
        gen_form.setSpacing(8)

        self._autostart_chk = QCheckBox("Daemon beim Anmelden automatisch starten (systemd)")
        self._autostart_chk.toggled.connect(self._on_autostart)
        gen_form.addRow("Autostart:", self._autostart_chk)

        self._lang_combo = QComboBox()
        self._lang_combo.addItem("Deutsch", "de")
        self._lang_combo.addItem("English (bald verfügbar)", "en")
        self._lang_combo.model().item(1).setEnabled(False)
        self._lang_combo.activated.connect(self._save_general)
        gen_form.addRow("Sprache:", self._lang_combo)
        layout.addWidget(general)

        # ── Bedienung ────────────────────────────────────────────────
        timing = QGroupBox("Bedienung (Multi-Press)")
        t_form = QFormLayout(timing)
        t_form.setSpacing(8)

        self._double_spin = QSpinBox()
        self._double_spin.setRange(100, 1000)
        self._double_spin.setSingleStep(50)
        self._double_spin.setSuffix(" ms")
        self._double_spin.setToolTip("Wartezeit auf einen zweiten Klick")
        self._double_spin.editingFinished.connect(self._save_general)
        t_form.addRow("Doppelklick-Fenster:", self._double_spin)

        self._hold_spin = QSpinBox()
        self._hold_spin.setRange(200, 2000)
        self._hold_spin.setSingleStep(100)
        self._hold_spin.setSuffix(" ms")
        self._hold_spin.setToolTip("Ab dieser Haltedauer zählt der Druck als „Halten“")
        self._hold_spin.editingFinished.connect(self._save_general)
        t_form.addRow("Halte-Dauer:", self._hold_spin)

        self._chain_spin = QSpinBox()
        self._chain_spin.setRange(0, 5000)
        self._chain_spin.setSingleStep(50)
        self._chain_spin.setSuffix(" ms")
        self._chain_spin.setToolTip("Pause zwischen den Aktionen einer Kette")
        self._chain_spin.editingFinished.connect(self._save_general)
        t_form.addRow("Ketten-Verzögerung:", self._chain_spin)
        layout.addWidget(timing)

        # ── Spotify ──────────────────────────────────────────────────
        spotify = QGroupBox("Spotify")
        sp_layout = QVBoxLayout(spotify)
        sp_layout.setSpacing(8)

        guide = QLabel(SPOTIFY_GUIDE)
        guide.setOpenExternalLinks(True)
        guide.setWordWrap(True)
        guide.setStyleSheet(f"color:{style.SUBTEXT};font-size:12px;")
        sp_layout.addWidget(guide)

        id_row = QHBoxLayout()
        id_row.addWidget(QLabel("Client-ID:"))
        self._client_id = QLineEdit()
        self._client_id.setPlaceholderText("Client-ID aus dem Spotify-Dashboard")
        self._client_id.editingFinished.connect(self._save_spotify)
        id_row.addWidget(self._client_id)
        sp_layout.addLayout(id_row)

        self._sp_status = QLabel()
        self._sp_status.setWordWrap(True)
        sp_layout.addWidget(self._sp_status)

        btn_row = QHBoxLayout()
        self._login_btn = QPushButton("Anmelden (Browser öffnet sich)")
        self._login_btn.setStyleSheet(
            f"QPushButton{{background:{style.GREEN};color:{style.BG};"
            f"font-weight:bold;border-radius:8px;padding:6px 14px;}}")
        self._login_btn.clicked.connect(self._spotify_login)
        btn_row.addWidget(self._login_btn)
        logout_btn = QPushButton("Abmelden")
        logout_btn.clicked.connect(self._spotify_logout)
        btn_row.addWidget(logout_btn)
        btn_row.addStretch()
        sp_layout.addLayout(btn_row)
        layout.addWidget(spotify)

        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        root.addWidget(scroll)

        self._bridge = _LoginBridge()
        self._bridge.done.connect(self._on_login_done)

    # ── Laden / Speichern ─────────────────────────────────────────────
    def reload(self):
        """Beim Öffnen der Seite aufrufen."""
        self._loading = True
        self.cfg = load_config()
        self._autostart_chk.setChecked(autostart.is_installed() and autostart.is_enabled())
        idx = self._lang_combo.findData(self.cfg.get("ui", {}).get("language", "de"))
        self._lang_combo.setCurrentIndex(max(0, idx))
        timing = self.cfg.get("timing", {})
        self._double_spin.setValue(timing.get("double_window_ms", 300))
        self._hold_spin.setValue(timing.get("hold_ms", 500))
        self._chain_spin.setValue(timing.get("chain_delay_ms", 0))
        self._client_id.setText(self.cfg.get("spotify", {}).get("client_id", ""))
        self._refresh_spotify_status()
        self._loading = False

    def _save_general(self):
        if self._loading:
            return
        self.cfg.setdefault("ui", {})["language"] = self._lang_combo.currentData()
        self.cfg.setdefault("timing", {})["double_window_ms"] = self._double_spin.value()
        self.cfg["timing"]["hold_ms"] = self._hold_spin.value()
        self.cfg["timing"]["chain_delay_ms"] = self._chain_spin.value()
        save_config(self.cfg)
        ipc_request({"cmd": "reload"}, timeout=1.0)

    def _on_autostart(self, enabled: bool):
        if self._loading:
            return
        try:
            if enabled:
                autostart.install()
            else:
                autostart.uninstall()
        except Exception as e:
            QMessageBox.warning(self, "Autostart", f"Fehler: {e}")

    # ── Spotify ───────────────────────────────────────────────────────
    def _save_spotify(self):
        if self._loading:
            return
        self.cfg.setdefault("spotify", {})["client_id"] = self._client_id.text().strip()
        save_config(self.cfg)

    def _refresh_spotify_status(self):
        client = SpotifyClient(self.cfg.get("spotify", {}).get("client_id", ""))
        if client.ready:
            self._sp_status.setText(f"<span style='color:{style.GREEN}'>✅ Verbunden</span>")
        else:
            self._sp_status.setText(f"<span style='color:{style.SUBTEXT}'>Noch nicht verbunden</span>")

    def _spotify_login(self):
        self._save_spotify()
        client_id = self._client_id.text().strip()
        if not client_id:
            self._sp_status.setText(f"<span style='color:{style.RED}'>Bitte zuerst die Client-ID eintragen.</span>")
            return
        self._login_btn.setEnabled(False)
        self._sp_status.setText("Warte auf Anmeldung im Browser…")
        redirect = self.cfg.get("spotify", {}).get("redirect_uri", "http://127.0.0.1:8888/callback")

        def worker():
            try:
                auth.login(client_id, redirect)
                self._bridge.done.emit(True, "")
            except Exception as e:
                self._bridge.done.emit(False, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_login_done(self, ok: bool, error: str):
        self._login_btn.setEnabled(True)
        if ok:
            ipc_request({"cmd": "reload"}, timeout=1.0)
            self._refresh_spotify_status()
        else:
            self._sp_status.setText(f"<span style='color:{style.RED}'>Fehler: {error}</span>")

    def _spotify_logout(self):
        auth.clear_token()
        ipc_request({"cmd": "reload"}, timeout=1.0)
        self._refresh_spotify_status()
