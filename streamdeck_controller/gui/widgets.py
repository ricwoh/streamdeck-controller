"""Gemeinsame GUI-Bausteine: Aktions-Palette (Drag-Quelle) und Tasten-Grid (Drop-Ziel)."""

from pathlib import Path

from PySide6.QtCore import QMimeData, QSize, Qt, Signal, QTimer
from PySide6.QtGui import QDrag, QIcon, QPixmap
from PySide6.QtWidgets import (
    QGridLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMenu, QPushButton, QVBoxLayout, QWidget,
)

from ..actions import ACTION_LIBRARY, CATEGORIES
from ..paths import resolve_icon
from . import style

MIME_ACTION = "application/x-streamdeck-action"
MIME_KEY = "application/x-streamdeck-key"


def icon_pixmap(ref: str, size: int = 48) -> QPixmap | None:
    path = resolve_icon(ref)
    if not path:
        return None
    px = QPixmap(str(path))
    if px.isNull():
        return None
    return px.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


# ── Aktions-Palette ────────────────────────────────────────────────────


class ActionPalette(QWidget):
    """Liste aller vorgefertigten Funktionen, gruppiert, per Drag & Drop nutzbar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QLabel("Funktionen")
        title.setStyleSheet(f"font-weight:bold;font-size:14px;color:{style.TEXT};")
        layout.addWidget(title)

        hint = QLabel("Auf eine Taste ziehen")
        hint.setStyleSheet(f"color:{style.SUBTEXT};font-size:11px;")
        layout.addWidget(hint)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Suchen…")
        self._search.textChanged.connect(self._refill)
        layout.addWidget(self._search)

        self._list = _DraggableActionList()
        layout.addWidget(self._list)
        self._refill()

    def _refill(self):
        query = self._search.text().strip().lower()
        self._list.clear()
        for category in CATEGORIES:
            actions = [a for a in ACTION_LIBRARY if a.category == category
                       and (not query or query in a.name.lower())]
            if not actions:
                continue
            header = QListWidgetItem(f"  {category}")
            header.setFlags(Qt.NoItemFlags)
            font = header.font()
            font.setBold(True)
            header.setFont(font)
            header.setForeground(Qt.gray)
            self._list.addItem(header)
            for spec in actions:
                item = QListWidgetItem(spec.name)
                item.setData(Qt.UserRole, spec.id)
                item.setToolTip(spec.description or spec.name)
                px = icon_pixmap(spec.icon, 24)
                if px:
                    item.setIcon(QIcon(px))
                self._list.addItem(item)


class _DraggableActionList(QListWidget):
    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        self.setIconSize(QSize(22, 22))

    def startDrag(self, actions):
        item = self.currentItem()
        if not item or not item.data(Qt.UserRole):
            return
        mime = QMimeData()
        mime.setData(MIME_ACTION, item.data(Qt.UserRole).encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        if not item.icon().isNull():
            drag.setPixmap(item.icon().pixmap(40, 40))
        drag.exec(Qt.CopyAction)


# ── Tasten-Grid ────────────────────────────────────────────────────────


class KeyButton(QPushButton):
    action_dropped = Signal(int, str)   # key_idx, action_id
    key_moved = Signal(int, int)        # from_idx, to_idx
    selected = Signal(int)
    clear_requested = Signal(int)

    BASE = (f"QPushButton{{background:{style.BG_ALT};border:2px solid {style.SURFACE};"
            f"border-radius:14px;color:{style.SUBTEXT};font-size:10px;}}"
            f"QPushButton:hover{{border:2px solid {style.SURFACE_HI};}}")
    SELECTED = (f"QPushButton{{background:{style.CARD};border:2px solid {style.ACCENT};"
                f"border-radius:14px;color:{style.ACCENT};font-size:10px;}}")
    DRAGOVER = (f"QPushButton{{background:{style.CARD};border:2px dashed {style.LAVENDER};"
                f"border-radius:14px;}}")
    FLASH = (f"QPushButton{{background:{style.SURFACE_HI};border:2px solid {style.LAVENDER};"
             f"border-radius:14px;}}")

    TILE = 84          # Standard-Kachelgröße
    TILE_COMPACT = 62  # Minimalansicht

    def __init__(self, idx: int, parent=None):
        super().__init__(parent)
        self.idx = idx
        self._is_selected = False
        self._has_content = False
        self.set_tile(self.TILE)
        self.setAcceptDrops(True)
        self.setStyleSheet(self.BASE)
        self.clicked.connect(lambda: self.selected.emit(self.idx))
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)

    def set_tile(self, size: int):
        self.setFixedSize(size, size)
        self.setIconSize(QSize(int(size * 0.76), int(size * 0.76)))

    def _context_menu(self, pos):
        menu = QMenu(self)
        clear = menu.addAction("Taste leeren")
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen == clear:
            self.clear_requested.emit(self.idx)

    def update_display(self, icon_ref: str, label: str):
        self._has_content = bool(icon_ref or label)
        px = icon_pixmap(icon_ref, 64)
        if px:
            self.setIcon(QIcon(px))
            self.setText("")
            self.setToolTip(label)
        else:
            self.setIcon(QIcon())
            self.setText(label or "")
            self.setToolTip("")

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self.setStyleSheet(self.SELECTED if selected else self.BASE)

    def flash(self):
        self.setStyleSheet(self.FLASH)
        QTimer.singleShot(180, lambda: self.set_selected(self._is_selected))

    # Drag-Ziel
    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if mime.hasFormat(MIME_ACTION) or mime.hasFormat(MIME_KEY):
            self.setStyleSheet(self.DRAGOVER)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.set_selected(self._is_selected)

    def dropEvent(self, event):
        self.set_selected(self._is_selected)
        mime = event.mimeData()
        if mime.hasFormat(MIME_ACTION):
            self.action_dropped.emit(self.idx, bytes(mime.data(MIME_ACTION)).decode())
            event.acceptProposedAction()
        elif mime.hasFormat(MIME_KEY):
            src = int(bytes(mime.data(MIME_KEY)).decode())
            if src != self.idx:
                self.key_moved.emit(src, self.idx)
            event.acceptProposedAction()

    # Drag-Quelle (Taste verschieben)
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._has_content:
            mime = QMimeData()
            mime.setData(MIME_KEY, str(self.idx).encode())
            drag = QDrag(self)
            drag.setMimeData(mime)
            if not self.icon().isNull():
                drag.setPixmap(self.icon().pixmap(48, 48))
            drag.exec(Qt.MoveAction)
        else:
            super().mouseMoveEvent(event)


class KeyGrid(QWidget):
    """Grid aller Deck-Tasten in Geräte-Anordnung."""

    action_dropped = Signal(int, str)
    key_moved = Signal(int, int)
    key_selected = Signal(int)
    key_clear = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setSpacing(10)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self.buttons: list[KeyButton] = []
        self.cols, self.rows = 0, 0
        self._compact = False

    def rebuild(self, cols: int, rows: int):
        if (cols, rows) == (self.cols, self.rows) and self.buttons:
            return
        self.cols, self.rows = cols, rows
        for btn in self.buttons:
            self._layout.removeWidget(btn)
            btn.deleteLater()
        self.buttons.clear()
        tile = KeyButton.TILE_COMPACT if self._compact else KeyButton.TILE
        for r in range(rows):
            for c in range(cols):
                idx = r * cols + c
                btn = KeyButton(idx)
                btn.set_tile(tile)
                btn.action_dropped.connect(self.action_dropped)
                btn.key_moved.connect(self.key_moved)
                btn.selected.connect(self.key_selected)
                btn.clear_requested.connect(self.key_clear)
                self._layout.addWidget(btn, r, c)
                self.buttons.append(btn)

    def set_compact(self, compact: bool):
        """Minimalansicht: kleinere Kacheln, damit nichts überlappt."""
        if compact == self._compact:
            return
        self._compact = compact
        self._layout.setSpacing(6 if compact else 10)
        tile = KeyButton.TILE_COMPACT if compact else KeyButton.TILE
        for btn in self.buttons:
            btn.set_tile(tile)

    def refresh(self, page: dict, selected: int | None):
        keys = page.get("keys", {})
        for btn in self.buttons:
            kc = keys.get(str(btn.idx), {})
            btn.update_display(kc.get("icon", ""), kc.get("label", ""))
            btn.set_selected(btn.idx == selected)
