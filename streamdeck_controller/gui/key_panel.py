"""Konfigurations-Panel für eine ausgewählte Taste.

Drei Trigger pro Taste: Drücken (1×), Doppelt (2×), Halten — jeweils mit
eigener Funktion und Parametern. Änderungen werden sofort gespeichert.
"""

from copy import deepcopy

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from ..actions import ACTION_LIBRARY, CATEGORIES, get_spec
from . import style
from .icon_picker import IconPicker
from .widgets import icon_pixmap

TRIGGERS = [("single", "Drücken"), ("double", "2× Drücken"), ("hold", "Halten")]


class TriggerEditor(QWidget):
    """Funktion + Parameter für einen Trigger (single/double/hold)."""

    changed = Signal()

    def __init__(self, trigger: str, parent=None):
        super().__init__(parent)
        self.trigger = trigger
        self._param_edits: dict[str, QLineEdit] = {}
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._combo = QComboBox()
        self._combo.addItem("— Keine Funktion —", "")
        for category in CATEGORIES:
            self._combo.insertSeparator(self._combo.count())
            header_idx = self._combo.count()
            self._combo.addItem(f"── {category} ──")
            self._combo.model().item(header_idx).setEnabled(False)
            for spec in ACTION_LIBRARY:
                if spec.category == category:
                    self._combo.addItem(spec.name, spec.id)
        self._combo.currentIndexChanged.connect(self._on_combo)
        layout.addWidget(self._combo)

        self._params_form = QFormLayout()
        self._params_form.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._params_form)

        self._hint = QLabel("")
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet(f"color:{style.SUBTEXT};font-size:11px;")
        layout.addWidget(self._hint)
        layout.addStretch()

    def load(self, action: dict | None):
        self._loading = True
        action_id = (action or {}).get("id", "")
        idx = self._combo.findData(action_id)
        self._combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._rebuild_params((action or {}).get("params", {}))
        self._loading = False

    def value(self) -> dict | None:
        action_id = self._combo.currentData()
        if not action_id:
            return None
        params = {}
        spec = get_spec(action_id)
        for p in (spec.params if spec else ()):
            text = self._param_edits.get(p.key)
            if text is None:
                continue
            value = text.text().strip()
            if p.kind == "int":
                try:
                    value = int(value)
                except ValueError:
                    value = 1
            params[p.key] = value
        return {"id": action_id, "params": params}

    def _on_combo(self):
        if self._loading:
            return
        self._rebuild_params({})
        self.changed.emit()

    def _rebuild_params(self, values: dict):
        while self._params_form.rowCount():
            self._params_form.removeRow(0)
        self._param_edits.clear()

        spec = get_spec(self._combo.currentData() or "")
        self._hint.setText(spec.description if spec else "")
        if not spec:
            return
        for p in spec.params:
            edit = QLineEdit()
            edit.setPlaceholderText(p.placeholder)
            edit.setText(str(values.get(p.key, "")))
            edit.editingFinished.connect(self.changed.emit)
            self._params_form.addRow(p.label + ":", edit)
            self._param_edits[p.key] = edit


class KeyConfigPanel(QWidget):
    """Rechtes Panel: Beschriftung, Trigger-Tabs, Icons. Speichert live."""

    changed = Signal()          # Konfiguration geändert → speichern + neu zeichnen

    def __init__(self, parent=None):
        super().__init__(parent)
        self._key_cfg: dict = {}
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._title = QLabel("Taste wählen oder Funktion hineinziehen")
        self._title.setStyleSheet(f"font-weight:bold;font-size:14px;color:{style.TEXT};")
        self._title.setWordWrap(True)
        layout.addWidget(self._title)

        form = QFormLayout()
        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("Text auf der Taste")
        self._label_edit.editingFinished.connect(self._on_change)
        form.addRow("Beschriftung:", self._label_edit)
        layout.addLayout(form)

        self._tabs = QTabWidget()
        self._editors: dict[str, TriggerEditor] = {}
        for trigger, title in TRIGGERS:
            editor = TriggerEditor(trigger)
            editor.changed.connect(self._on_change)
            self._editors[trigger] = editor
            self._tabs.addTab(editor, title)
        layout.addWidget(self._tabs)

        icons = QGroupBox("Tastengrafik")
        grid = QVBoxLayout(icons)
        self._icon_rows: dict[str, tuple[QLabel, str]] = {}
        for which, label in (("icon", "Normal"), ("icon_active", "Aktiv")):
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{label}:"))
            preview = QLabel()
            preview.setFixedSize(44, 44)
            preview.setStyleSheet(f"background:{style.SURFACE};border-radius:6px;")
            preview.setAlignment(Qt.AlignCenter)
            row.addWidget(preview)
            pick = QPushButton("Wählen…")
            pick.clicked.connect(lambda _, w=which: self._pick_icon(w))
            row.addWidget(pick)
            clear = QPushButton("✕")
            clear.setFixedWidth(30)
            clear.clicked.connect(lambda _, w=which: self._set_icon(w, ""))
            row.addWidget(clear)
            row.addStretch()
            grid.addLayout(row)
            self._icon_rows[which] = preview
        hint = QLabel("„Aktiv“ wird bei Umschalt-Funktionen gezeigt (z.B. Play/Pause).")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{style.SUBTEXT};font-size:11px;")
        grid.addWidget(hint)
        layout.addWidget(icons)

        self._clear_btn = QPushButton("Taste leeren")
        self._clear_btn.setStyleSheet(
            f"QPushButton{{color:{style.RED};border:1px solid {style.RED};"
            f"border-radius:4px;padding:5px;}}")
        self._clear_btn.clicked.connect(self._clear_key)
        layout.addWidget(self._clear_btn)
        layout.addStretch()

        self.setEnabled(False)

    # ── Laden / Speichern ─────────────────────────────────────────────
    def load_key(self, key_idx: int, key_cfg: dict):
        self._loading = True
        self._key_cfg = deepcopy(key_cfg)
        self.setEnabled(True)
        self._title.setText(f"Taste {key_idx + 1}")

        self._label_edit.setText(key_cfg.get("label", ""))
        actions = key_cfg.get("actions", {})
        for trigger, editor in self._editors.items():
            editor.load(actions.get(trigger))
        for which in ("icon", "icon_active"):
            self._update_preview(which, key_cfg.get(which, ""))
        self._loading = False

    def clear_selection(self):
        self._loading = True
        self._key_cfg = {}
        self._title.setText("Taste wählen oder Funktion hineinziehen")
        self._label_edit.setText("")
        for editor in self._editors.values():
            editor.load(None)
        for which in ("icon", "icon_active"):
            self._update_preview(which, "")
        self.setEnabled(False)
        self._loading = False

    def current_key_cfg(self) -> dict:
        """Aktuellen Panel-Zustand als Key-Konfiguration ausgeben."""
        kc = {}
        label = self._label_edit.text().strip()
        if label:
            kc["label"] = label
        actions = {}
        for trigger, editor in self._editors.items():
            value = editor.value()
            if value:
                actions[trigger] = value
        if actions:
            kc["actions"] = actions
        for which in ("icon", "icon_active"):
            ref = self._key_cfg.get(which, "")
            if ref:
                kc[which] = ref
        return kc

    def _on_change(self):
        if not self._loading:
            self.changed.emit()

    # ── Icons ─────────────────────────────────────────────────────────
    def _pick_icon(self, which: str):
        picker = IconPicker(self)
        if picker.exec() and picker.selected_ref:
            self._set_icon(which, picker.selected_ref)

    def _set_icon(self, which: str, ref: str):
        if ref:
            self._key_cfg[which] = ref
        else:
            self._key_cfg.pop(which, None)
        self._update_preview(which, ref)
        self._on_change()

    def _update_preview(self, which: str, ref: str):
        preview = self._icon_rows[which]
        px = icon_pixmap(ref, 40) if ref else None
        preview.setPixmap(px or QPixmap())

    def _clear_key(self):
        self._loading = True
        self._label_edit.setText("")
        for editor in self._editors.values():
            editor.load(None)
        self._key_cfg = {}
        for which in ("icon", "icon_active"):
            self._update_preview(which, "")
        self._loading = False
        self.changed.emit()
