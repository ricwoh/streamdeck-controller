"""Konfigurations-Panel für eine ausgewählte Taste.

Drei Trigger pro Taste (Drücken / 2× / Halten), jeder Trigger kann eine
Aktionskette tragen: per „+“ kommt eine zweite Aktion dazu (geteilte Breite),
ab drei Aktionen wechselt die Ansicht in eine nummerierte Ketten-Leiste
(1 → 2 → 3 …) mit Editor für den gewählten Schritt.
"""

from copy import deepcopy

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from ..actions import ACTION_LIBRARY, CATEGORIES, get_spec
from . import style
from .icon_picker import IconPicker
from .widgets import icon_pixmap

TRIGGERS = [("single", "Drücken"), ("double", "2× Drücken"), ("hold", "Halten")]
MAX_ACTIONS = 6

_SMALL = "padding:2px;font-weight:bold;"


class ActionStepEditor(QWidget):
    """Eine Aktion: Funktions-Dropdown + Parameter."""

    changed = Signal()

    def __init__(self, pages_provider=None, parent=None):
        super().__init__(parent)
        self._pages_provider = pages_provider or (lambda: [])
        self._param_edits: dict[str, QWidget] = {}
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

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
        self._params_form.setSpacing(4)
        layout.addLayout(self._params_form)

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
            widget = self._param_edits.get(p.key)
            if widget is None:
                continue
            if p.kind == "page":
                params[p.key] = widget.currentIndex() + 1  # 1-basiert
                continue
            value = widget.text().strip()
            if p.kind == "int":
                try:
                    value = int(value)
                except ValueError:
                    value = 1
            params[p.key] = value
        return {"id": action_id, "params": params}

    def title(self) -> str:
        spec = get_spec(self._combo.currentData() or "")
        return spec.name if spec else "—"

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
        if not spec:
            return
        self.setToolTip(spec.description or spec.name)
        for p in spec.params:
            if p.kind == "page":
                combo = QComboBox()
                for i, name in enumerate(self._pages_provider()):
                    combo.addItem(f"{i + 1} — {name}")
                try:
                    target = int(values.get(p.key, 1))
                except (TypeError, ValueError):
                    target = 1
                combo.setCurrentIndex(max(0, min(target - 1, combo.count() - 1)))
                combo.activated.connect(lambda *_: self.changed.emit())
                self._params_form.addRow(p.label + ":", combo)
                self._param_edits[p.key] = combo
                continue
            edit = QLineEdit()
            edit.setPlaceholderText(p.placeholder)
            edit.setText(str(values.get(p.key, "")))
            edit.editingFinished.connect(self.changed.emit)
            self._params_form.addRow(p.label + ":", edit)
            self._param_edits[p.key] = edit


class TriggerEditor(QWidget):
    """Aktionskette für einen Trigger (single/double/hold)."""

    changed = Signal()

    def __init__(self, trigger: str, pages_provider=None, parent=None):
        super().__init__(parent)
        self.trigger = trigger
        self._pages_provider = pages_provider or (lambda: [])
        self._steps: list[ActionStepEditor] = []
        self._selected_step = 0
        self._loading = False

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(8, 8, 8, 8)
        self._root.setSpacing(6)
        self.load(None)

    # ── Laden / Wert ──────────────────────────────────────────────────
    def load(self, action):
        """action: None | dict | list[dict]"""
        self._loading = True
        if action is None:
            values = [None]
        elif isinstance(action, list):
            values = action or [None]
        else:
            values = [action]
        self._selected_step = 0
        self._build_steps(values)
        self._loading = False

    def value(self):
        """None | dict (eine Aktion) | list[dict] (Kette)"""
        actions = [v for v in (s.value() for s in self._steps) if v]
        if not actions:
            return None
        if len(actions) == 1:
            return actions[0]
        return actions

    # ── Aufbau ────────────────────────────────────────────────────────
    def _clear_layout(self):
        while self._root.count():
            item = self._root.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout():
                self._clear_sub(item.layout())

    def _clear_sub(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout():
                self._clear_sub(item.layout())
        layout.deleteLater()

    def _make_steps(self, values) -> list[ActionStepEditor]:
        steps = []
        for v in values:
            step = ActionStepEditor(pages_provider=self._pages_provider)
            step.load(v)
            step.changed.connect(self._on_step_changed)
            steps.append(step)
        return steps

    def _build_steps(self, values):
        self._clear_layout()
        self._steps = self._make_steps(values)
        if len(self._steps) <= 2:
            self._build_compact()
        else:
            self._build_chain()

    def _build_compact(self):
        """1–2 Aktionen: nebeneinander, + zum Erweitern, ✕ zum Entfernen."""
        row = QHBoxLayout()
        row.setSpacing(8)
        for i, step in enumerate(self._steps):
            box = QVBoxLayout()
            box.setSpacing(4)
            if len(self._steps) > 1:
                head = QHBoxLayout()
                num = QLabel(f"Aktion {i + 1}")
                num.setStyleSheet(f"color:{style.SUBTEXT};font-size:11px;font-weight:bold;")
                head.addWidget(num)
                head.addStretch()
                rm = QPushButton("✕")
                rm.setFixedSize(22, 22)
                rm.setStyleSheet(_SMALL)
                rm.setToolTip("Aktion entfernen")
                rm.clicked.connect(lambda _, idx=i: self._remove_step(idx))
                head.addWidget(rm)
                box.addLayout(head)
            box.addWidget(step)
            box.addStretch()
            row.addLayout(box, stretch=1)

        add = QPushButton("+")
        add.setFixedSize(26, 26)
        add.setStyleSheet(_SMALL)
        add.setToolTip("Weitere Aktion hinzufügen (Kette)")
        add.clicked.connect(self._add_step)
        add_box = QVBoxLayout()
        add_box.addWidget(add)
        add_box.addStretch()
        row.addLayout(add_box)
        self._root.addLayout(row)
        self._root.addStretch()

    def _build_chain(self):
        """3+ Aktionen: nummerierte Ketten-Leiste 1 → 2 → 3, Editor darunter."""
        chips = QHBoxLayout()
        chips.setSpacing(4)
        label = QLabel("Kette:")
        label.setStyleSheet(f"color:{style.SUBTEXT};font-size:11px;font-weight:bold;")
        chips.addWidget(label)
        for i, step in enumerate(self._steps):
            if i:
                arrow = QLabel("→")
                arrow.setStyleSheet(f"color:{style.SUBTEXT};")
                chips.addWidget(arrow)
            chip = QPushButton(str(i + 1))
            chip.setFixedSize(26, 26)
            chip.setToolTip(step.title())
            selected = i == self._selected_step
            chip.setStyleSheet(
                f"padding:0;border-radius:13px;font-weight:bold;"
                + (f"background:{style.ACCENT};color:{style.BG};border:none;"
                   if selected else ""))
            chip.clicked.connect(lambda _, idx=i: self._select_step(idx))
            chips.addWidget(chip)
        add = QPushButton("+")
        add.setFixedSize(26, 26)
        add.setStyleSheet(_SMALL)
        add.setToolTip("Weitere Aktion hinzufügen")
        if len(self._steps) >= MAX_ACTIONS:
            add.setEnabled(False)
        add.clicked.connect(self._add_step)
        chips.addWidget(add)
        chips.addStretch()
        self._root.addLayout(chips)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color:{style.SURFACE};")
        self._root.addWidget(sep)

        # Editor des gewählten Schritts + Werkzeuge
        current = self._steps[self._selected_step]
        head = QHBoxLayout()
        title = QLabel(f"Aktion {self._selected_step + 1} von {len(self._steps)}")
        title.setStyleSheet(f"color:{style.TEXT};font-size:11px;font-weight:bold;")
        head.addWidget(title)
        head.addStretch()
        for text, tip, handler, enabled in (
            ("↑", "Nach vorne schieben", lambda: self._move_step(-1), self._selected_step > 0),
            ("↓", "Nach hinten schieben", lambda: self._move_step(+1),
             self._selected_step < len(self._steps) - 1),
            ("✕", "Aktion entfernen", lambda: self._remove_step(self._selected_step), True),
        ):
            btn = QPushButton(text)
            btn.setFixedSize(22, 22)
            btn.setStyleSheet(_SMALL)
            btn.setToolTip(tip)
            btn.setEnabled(enabled)
            btn.clicked.connect(handler)
            head.addWidget(btn)
        self._root.addLayout(head)
        self._root.addWidget(current)
        self._root.addStretch()

    # ── Ketten-Operationen ────────────────────────────────────────────
    def _current_values(self) -> list:
        return [s.value() for s in self._steps]

    def _add_step(self):
        if len(self._steps) >= MAX_ACTIONS:
            return
        values = self._current_values() + [None]
        self._selected_step = len(values) - 1
        self._build_steps(values)
        # noch keine Funktion gewählt → kein changed nötig

    def _remove_step(self, idx: int):
        values = self._current_values()
        values.pop(idx)
        if not values:
            values = [None]
        self._selected_step = max(0, min(self._selected_step, len(values) - 1))
        self._build_steps(values)
        self._emit_changed()

    def _move_step(self, delta: int):
        values = self._current_values()
        i, j = self._selected_step, self._selected_step + delta
        if 0 <= j < len(values):
            values[i], values[j] = values[j], values[i]
            self._selected_step = j
            self._build_steps(values)
            self._emit_changed()

    def _select_step(self, idx: int):
        self._selected_step = idx
        self._build_steps(self._current_values())

    def _on_step_changed(self):
        # Bei 3+ Aktionen Tooltips/Chips aktuell halten
        if len(self._steps) > 2 and not self._loading:
            values = self._current_values()
            self._build_steps(values)
        self._emit_changed()

    def _emit_changed(self):
        if not self._loading:
            self.changed.emit()


class KeyConfigPanel(QWidget):
    """Panel unter dem Grid: Beschriftung, Trigger-Tabs, Icons. Speichert live."""

    changed = Signal()

    def __init__(self, pages_provider=None, parent=None):
        super().__init__(parent)
        self._key_cfg: dict = {}
        self._loading = False
        self._pages_provider = pages_provider

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        head = QHBoxLayout()
        self._title = QLabel("Taste wählen oder Funktion hineinziehen")
        self._title.setStyleSheet(f"font-weight:bold;font-size:14px;color:{style.TEXT};")
        head.addWidget(self._title)
        head.addStretch()
        self._clear_btn = QPushButton("Taste leeren")
        self._clear_btn.setStyleSheet(
            f"QPushButton{{color:{style.RED};border:1px solid {style.RED};"
            f"border-radius:6px;padding:3px 10px;}}")
        self._clear_btn.clicked.connect(self._clear_key)
        head.addWidget(self._clear_btn)
        layout.addLayout(head)

        form = QFormLayout()
        form.setSpacing(4)
        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("Text auf der Taste")
        self._label_edit.editingFinished.connect(self._on_change)
        form.addRow("Beschriftung:", self._label_edit)
        layout.addLayout(form)

        self._tabs = QTabWidget()
        self._editors: dict[str, TriggerEditor] = {}
        for trigger, title in TRIGGERS:
            editor = TriggerEditor(trigger, pages_provider=self._pages_provider)
            editor.changed.connect(self._on_change)
            self._editors[trigger] = editor
            self._tabs.addTab(editor, title)
        layout.addWidget(self._tabs, stretch=1)

        icons = QGroupBox("Tastengrafik")
        icon_row = QHBoxLayout(icons)
        icon_row.setSpacing(10)
        self._icon_rows: dict[str, QLabel] = {}
        for which, label in (("icon", "Normal"), ("icon_active", "Aktiv")):
            icon_row.addWidget(QLabel(f"{label}:"))
            preview = QLabel()
            preview.setFixedSize(40, 40)
            preview.setStyleSheet(f"background:{style.SURFACE};border-radius:6px;")
            preview.setAlignment(Qt.AlignCenter)
            icon_row.addWidget(preview)
            pick = QPushButton("Wählen…")
            pick.clicked.connect(lambda _, w=which: self._pick_icon(w))
            icon_row.addWidget(pick)
            clear = QPushButton("✕")
            clear.setFixedSize(24, 24)
            clear.setStyleSheet(_SMALL)
            clear.clicked.connect(lambda _, w=which: self._set_icon(w, ""))
            icon_row.addWidget(clear)
            self._icon_rows[which] = preview
        icon_row.addStretch()
        layout.addWidget(icons)

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
        px = icon_pixmap(ref, 36) if ref else None
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
