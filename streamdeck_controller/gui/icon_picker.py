"""Icon-Auswahl mit Icon-Packs (Ordner), Suche und einklappbaren Sektionen.

Packs:
- „Standard“        → icons/builtin (generierte Funktions-Icons)
- „Eigene“          → lose Dateien in icons/ und ~/.config/streamdeck/icons/
- jeder Unterordner → eigenes Pack (einfach Ordner mit PNGs ablegen)

Der Zustand (gewähltes Pack, eingeklappte Sektionen, Suche) wird in der
Konfiguration gespeichert und beim nächsten Öffnen wiederhergestellt.
"""

import math
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from ..config import load_config, save_config
from ..paths import BUILTIN_ICONS_DIR, ICONS_DIR, USER_ICONS_DIR
from . import style
from .widgets import icon_pixmap

ALL_PACKS = "Alle Packs"
GRID_W, GRID_H = 88, 92


def discover_packs() -> dict[str, list[tuple[str, str]]]:
    """Packs sammeln: {Packname: [(Anzeigename, Icon-Referenz), …]}"""
    packs: dict[str, list[tuple[str, str]]] = {}

    def add(pack: str, name: str, ref: str):
        packs.setdefault(pack, [])
        if not any(r == ref for _, r in packs[pack]):
            packs[pack].append((name, ref))

    if BUILTIN_ICONS_DIR.is_dir():
        for p in sorted(BUILTIN_ICONS_DIR.glob("*.png")):
            add("Standard", p.stem, f"builtin:{p.stem}")

    for base in (ICONS_DIR, USER_ICONS_DIR):
        if not base.is_dir():
            continue
        for p in sorted(base.glob("*.png")):
            add("Eigene", p.stem, str(p))
        for sub in sorted(d for d in base.iterdir() if d.is_dir() and d.name != "builtin"):
            for p in sorted(sub.glob("*.png")):
                add(sub.name, p.stem, str(p))
    return packs


class _PackList(QListWidget):
    """Icon-Grid eines Packs; Höhe passt sich dem Inhalt an (kein Eigen-Scroll)."""

    def __init__(self):
        super().__init__()
        self.setViewMode(QListWidget.IconMode)
        self.setIconSize(QSize(56, 56))
        self.setGridSize(QSize(GRID_W, GRID_H))
        self.setResizeMode(QListWidget.Adjust)
        self.setUniformItemSizes(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("QListWidget{border:none;background:transparent;}")

    def _update_height(self):
        cols = max(1, self.viewport().width() // GRID_W)
        rows = math.ceil(self.count() / cols) if self.count() else 0
        self.setFixedHeight(rows * GRID_H + 8)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_height()


class _PackSection(QWidget):
    """Einklappbare Sektion: Kopfzeile (▾ Name (n)) + Icon-Grid."""

    toggled = Signal(str, bool)        # pack, collapsed
    item_clicked = Signal(object)      # QListWidgetItem
    item_activated = Signal(object)    # Doppelklick

    def __init__(self, pack: str, collapsed: bool = False, parent=None):
        super().__init__(parent)
        self.pack = pack
        self._collapsed = collapsed

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._header = QPushButton()
        self._header.setCursor(Qt.PointingHandCursor)
        self._header.setStyleSheet(
            f"QPushButton{{text-align:left;background:{style.CARD};color:{style.SUBTEXT};"
            f"border:none;border-radius:6px;padding:5px 10px;font-weight:bold;}}"
            f"QPushButton:hover{{color:{style.ACCENT};}}")
        self._header.clicked.connect(self._toggle)
        layout.addWidget(self._header)

        self.list = _PackList()
        self.list.itemClicked.connect(self.item_clicked.emit)
        self.list.itemDoubleClicked.connect(self.item_activated.emit)
        layout.addWidget(self.list)
        self.list.setVisible(not collapsed)

    def fill(self, entries: list[tuple[str, str]], query: str):
        self.list.clear()
        for name, ref in entries:
            if query and query not in name.lower():
                continue
            px = icon_pixmap(ref, 56)
            if not px:
                continue
            item = QListWidgetItem(QIcon(px), name)
            item.setData(Qt.UserRole, ref)
            item.setToolTip(f"{name}  [{self.pack}]")
            self.list.addItem(item)
        self._refresh_header()
        self.list._update_height()
        self.setVisible(self.list.count() > 0)

    def _refresh_header(self):
        arrow = "▸" if self._collapsed else "▾"
        self._header.setText(f"{arrow}  {self.pack}  ({self.list.count()})")

    def _toggle(self):
        self._collapsed = not self._collapsed
        self.list.setVisible(not self._collapsed)
        self._refresh_header()
        self.toggled.emit(self.pack, self._collapsed)


class IconPicker(QDialog):
    """Liefert in .selected_ref eine Icon-Referenz ('builtin:play' oder Pfad)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Icon wählen")
        self.setMinimumSize(580, 480)
        self.selected_ref: str | None = None
        self._packs = discover_packs()
        self._current_item = None

        self._cfg = load_config()
        state = self._cfg.get("ui", {}).get("icon_picker", {})
        self._collapsed: set[str] = set(state.get("collapsed", []))
        saved_pack = state.get("pack")
        saved_search = state.get("search", "")

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        top = QHBoxLayout()
        self._pack_combo = QComboBox()
        self._pack_combo.addItem(ALL_PACKS)
        for pack in self._packs:
            self._pack_combo.addItem(f"{pack}  ({len(self._packs[pack])})", pack)
        if saved_pack:
            idx = self._pack_combo.findData(saved_pack)
            if idx >= 0:
                self._pack_combo.setCurrentIndex(idx)
        self._pack_combo.currentIndexChanged.connect(self._refill)
        top.addWidget(self._pack_combo, stretch=1)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Suchen…")
        self._search.setClearButtonEnabled(True)
        self._search.setText(saved_search)
        self._search.textChanged.connect(self._refill)
        top.addWidget(self._search, stretch=2)
        layout.addLayout(top)

        self._sections: dict[str, _PackSection] = {}
        body = QWidget()
        self._body_layout = QVBoxLayout(body)
        self._body_layout.setContentsMargins(0, 0, 4, 0)
        self._body_layout.setSpacing(6)
        for pack in self._packs:
            section = _PackSection(pack, collapsed=pack in self._collapsed)
            section.toggled.connect(self._on_section_toggled)
            section.item_clicked.connect(self._on_item_clicked)
            section.item_activated.connect(self._on_item_activated)
            self._sections[pack] = section
            self._body_layout.addWidget(section)
        self._body_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        layout.addWidget(scroll, stretch=1)

        row = QHBoxLayout()
        browse = QPushButton("Eigene Datei…")
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        hint = QLabel("Packs = Ordner unter ~/.config/streamdeck/icons/")
        hint.setStyleSheet(f"color:{style.SUBTEXT};font-size:11px;")
        row.addWidget(hint)
        row.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        row.addWidget(buttons)
        layout.addLayout(row)

        self._refill()

    # ── Befüllen ──────────────────────────────────────────────────────
    def _refill(self):
        query = self._search.text().strip().lower()
        selected_pack = self._pack_combo.currentData()
        for pack, section in self._sections.items():
            if selected_pack and pack != selected_pack:
                section.setVisible(False)
                continue
            section.fill(self._packs[pack], query)

    # ── Auswahl ───────────────────────────────────────────────────────
    def _on_item_clicked(self, item):
        # Auswahl in den anderen Sektionen aufheben
        self._current_item = item
        for section in self._sections.values():
            if item.listWidget() is not section.list:
                section.list.clearSelection()

    def _on_item_activated(self, item):
        self._current_item = item
        self.accept()

    def _on_section_toggled(self, pack: str, collapsed: bool):
        if collapsed:
            self._collapsed.add(pack)
        else:
            self._collapsed.discard(pack)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Icon wählen", str(Path.home()),
            "Bilder (*.png *.jpg *.jpeg *.webp *.svg)")
        if path:
            self.selected_ref = path
            self._save_state()
            QDialog.accept(self)

    # ── Zustand speichern ─────────────────────────────────────────────
    def _save_state(self):
        cfg = load_config()
        cfg.setdefault("ui", {})["icon_picker"] = {
            "pack": self._pack_combo.currentData(),
            "collapsed": sorted(self._collapsed),
            "search": self._search.text(),
        }
        save_config(cfg)

    def accept(self):
        if self._current_item:
            self.selected_ref = self._current_item.data(Qt.UserRole)
        self._save_state()
        QDialog.accept(self)

    def reject(self):
        self._save_state()
        QDialog.reject(self)
