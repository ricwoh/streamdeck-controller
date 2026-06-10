"""Icon-Auswahl mit Icon-Packs (Ordner) und Suche — angelehnt an Elgato.

Packs:
- „Standard“        → icons/builtin (generierte Funktions-Icons)
- „Eigene“          → lose Dateien in icons/ und ~/.config/streamdeck/icons/
- jeder Unterordner → eigenes Pack (einfach Ordner mit PNGs ablegen/importieren)
"""

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout,
)

from ..paths import BUILTIN_ICONS_DIR, ICONS_DIR, USER_ICONS_DIR
from .widgets import icon_pixmap

ALL_PACKS = "Alle Packs"


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


class IconPicker(QDialog):
    """Liefert in .selected_ref eine Icon-Referenz ('builtin:play' oder Pfad)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Icon wählen")
        self.setMinimumSize(560, 460)
        self.selected_ref: str | None = None
        self._packs = discover_packs()

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        top = QHBoxLayout()
        self._pack_combo = QComboBox()
        self._pack_combo.addItem(ALL_PACKS)
        for pack in self._packs:
            self._pack_combo.addItem(f"{pack}  ({len(self._packs[pack])})", pack)
        self._pack_combo.currentIndexChanged.connect(self._refill)
        top.addWidget(self._pack_combo, stretch=1)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Suchen…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._refill)
        top.addWidget(self._search, stretch=2)
        layout.addLayout(top)

        self._list = QListWidget()
        self._list.setViewMode(QListWidget.IconMode)
        self._list.setIconSize(QSize(56, 56))
        self._list.setGridSize(QSize(88, 92))
        self._list.setResizeMode(QListWidget.Adjust)
        self._list.setUniformItemSizes(True)
        self._list.itemDoubleClicked.connect(lambda _: self.accept())
        layout.addWidget(self._list)

        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("color:#a6adc8;font-size:11px;")
        layout.addWidget(self._count_lbl)

        row = QHBoxLayout()
        browse = QPushButton("Eigene Datei…")
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        hint = QLabel("Packs = Ordner unter ~/.config/streamdeck/icons/")
        hint.setStyleSheet("color:#a6adc8;font-size:11px;")
        row.addWidget(hint)
        row.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        row.addWidget(buttons)
        layout.addLayout(row)

        self._refill()

    def _refill(self):
        query = self._search.text().strip().lower()
        selected_pack = self._pack_combo.currentData()
        self._list.clear()
        shown = 0
        for pack, entries in self._packs.items():
            if selected_pack and pack != selected_pack:
                continue
            for name, ref in entries:
                if query and query not in name.lower():
                    continue
                px = icon_pixmap(ref, 56)
                if not px:
                    continue
                item = QListWidgetItem(QIcon(px), name)
                item.setData(Qt.UserRole, ref)
                item.setToolTip(f"{name}  [{pack}]")
                self._list.addItem(item)
                shown += 1
        self._count_lbl.setText(f"{shown} Icons")

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Icon wählen", str(Path.home()),
            "Bilder (*.png *.jpg *.jpeg *.webp *.svg)")
        if path:
            self.selected_ref = path
            QDialog.accept(self)

    def accept(self):
        item = self._list.currentItem()
        if item:
            self.selected_ref = item.data(Qt.UserRole)
        QDialog.accept(self)
