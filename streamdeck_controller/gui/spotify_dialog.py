"""Spotify-Einrichtung in der GUI: Client-ID eintragen + Login per Browser."""

import threading

from PySide6.QtCore import Signal, QObject
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout,
)

from ..config import save_config
from ..ipc import ipc_request
from ..spotify import SpotifyClient, auth
from . import style

GUIDE = """\
<b>Einmalige Einrichtung:</b><br>
1. <a href="https://developer.spotify.com/dashboard">developer.spotify.com/dashboard</a> öffnen und einloggen<br>
2. „Create app“ — Name egal,<br>
&nbsp;&nbsp;&nbsp;Redirect URI: <code>http://127.0.0.1:8888/callback</code><br>
3. API: „Web API“ auswählen<br>
4. Client-ID aus den App-Einstellungen kopieren und unten einfügen
"""


class _LoginBridge(QObject):
    done = Signal(bool, str)


class SpotifyDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("Spotify verbinden")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        guide = QLabel(GUIDE)
        guide.setOpenExternalLinks(True)
        guide.setWordWrap(True)
        layout.addWidget(guide)

        form = QFormLayout()
        self._client_id = QLineEdit(cfg.get("spotify", {}).get("client_id", ""))
        self._client_id.setPlaceholderText("Client-ID")
        form.addRow("Client-ID:", self._client_id)
        layout.addLayout(form)

        self._status = QLabel()
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        row = QHBoxLayout()
        self._login_btn = QPushButton("Anmelden (Browser öffnet sich)")
        self._login_btn.setStyleSheet(
            f"QPushButton{{background:{style.GREEN};color:{style.BG};"
            f"font-weight:bold;border-radius:4px;padding:6px;}}")
        self._login_btn.clicked.connect(self._login)
        row.addWidget(self._login_btn)
        logout_btn = QPushButton("Abmelden")
        logout_btn.clicked.connect(self._logout)
        row.addWidget(logout_btn)
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        row.addWidget(close_btn)
        layout.addLayout(row)

        self._bridge = _LoginBridge()
        self._bridge.done.connect(self._on_login_done)
        self._refresh_status()

    def _refresh_status(self):
        sp_cfg = self.cfg.get("spotify", {})
        client = SpotifyClient(sp_cfg.get("client_id", ""), sp_cfg.get("client_secret", ""))
        if client.ready:
            self._status.setText(f"<span style='color:{style.GREEN}'>✅ Verbunden</span>")
        else:
            self._status.setText(f"<span style='color:{style.SUBTEXT}'>Noch nicht verbunden</span>")

    def _save_client_id(self) -> str:
        client_id = self._client_id.text().strip()
        self.cfg.setdefault("spotify", {})["client_id"] = client_id
        save_config(self.cfg)
        return client_id

    def _login(self):
        client_id = self._save_client_id()
        if not client_id:
            self._status.setText(f"<span style='color:{style.RED}'>Bitte zuerst die Client-ID eintragen.</span>")
            return
        self._login_btn.setEnabled(False)
        self._status.setText("Warte auf Anmeldung im Browser…")
        sp_cfg = self.cfg.get("spotify", {})

        def worker():
            try:
                auth.login(client_id, sp_cfg.get("client_secret", ""),
                           sp_cfg.get("redirect_uri", "http://127.0.0.1:8888/callback"))
                self._bridge.done.emit(True, "")
            except Exception as e:
                self._bridge.done.emit(False, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_login_done(self, ok: bool, error: str):
        self._login_btn.setEnabled(True)
        if ok:
            ipc_request({"cmd": "reload"})
            self._refresh_status()
        else:
            self._status.setText(f"<span style='color:{style.RED}'>Fehler: {error}</span>")

    def _logout(self):
        auth.clear_token()
        ipc_request({"cmd": "reload"})
        self._refresh_status()
