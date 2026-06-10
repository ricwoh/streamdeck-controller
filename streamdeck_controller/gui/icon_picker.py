"""Icon-Auswahl: mitgelieferte Icons als Galerie + eigene Datei wählen."""

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout,
)

from ..paths import BUILTIN_ICONS_DIR, ICONS_DIR, USER_ICONS_DIR
from .widgets import icon_pixmap


class IconPicker(QDialog):
    """Liefert in .selected_ref eine Icon-Referenz ('builtin:play' oder Pfad)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Icon wählen")
        self.setMinimumSize(520, 420)
        self.selected_ref: str | None = None

        layout = QVBoxLayout(self)
        self._list = QListWidget()
        self._list.setViewMode(QListWidget.IconMode)
        self._list.setIconSize(QSize(56, 56))
        self._list.setGridSize(QSize(84, 84))
        self._list.setResizeMode(QListWidget.Adjust)
        self._list.setUniformItemSizes(True)
        self._list.itemDoubleClicked.connect(lambda _: self.accept())
        layout.addWidget(self._list)

        row = QHBoxLayout()
        browse = QPushButton("Eigene Datei…")
        browse.clicked.connect(self._browse)
        row.addWidget(browse)
        row.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        row.addWidget(buttons)
        layout.addLayout(row)

        self._fill()

    def _fill(self):
        seen = set()
        sources = [
            (BUILTIN_ICONS_DIR, "builtin:{stem}"),
            (USER_ICONS_DIR, "{path}"),
            (ICONS_DIR, "{path}"),
        ]
        for base, pattern in sources:
            if not base.is_dir():
                continue
            for path in sorted(base.glob("*.png")):
                ref = pattern.format(stem=path.stem, path=str(path))
                if ref in seen:
                    continue
                seen.add(ref)
                px = icon_pixmap(ref, 56)
                if not px:
                    continue
                item = QListWidgetItem(QIcon(px), path.stem)
                item.setData(Qt.UserRole, ref)
                item.setToolTip(path.stem)
                self._list.addItem(item)

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
