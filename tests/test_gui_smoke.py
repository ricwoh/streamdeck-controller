"""GUI-Smoke-Test (offscreen): Fenster baut sich auf, Drag&Drop-Logik greift."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    from streamdeck_controller import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "CONFIG_PATH", tmp_path / "config.json")
    from streamdeck_controller.gui import main_window as mw
    monkeypatch.setattr(mw, "ipc_request", lambda *a, **k: None)
    monkeypatch.setattr(mw, "enumerate_decks", lambda: [])
    win = mw.MainWindow()
    yield win
    win._status_timer.stop()
    win.close()


def test_window_builds_with_mini_grid(window):
    assert len(window.grid.buttons) == 6  # Mini-Standard 3x2
    assert window._page_bar.count() == 1


def test_drop_action_assigns_key(window):
    window._on_action_dropped(0, "spotify_play_pause")
    kc = window.cfg["pages"][0]["keys"]["0"]
    assert kc["actions"]["single"]["id"] == "spotify_play_pause"
    assert kc["icon"] == "builtin:spotify_play_pause"
    assert kc["icon_active"] == "builtin:spotify_play_pause_active"
    assert window.selected_key == 0


def test_move_key(window):
    window._on_action_dropped(0, "sys_lock")
    window._on_key_moved(0, 5)
    keys = window.cfg["pages"][0]["keys"]
    assert keys.get("5", {}).get("actions", {}).get("single", {}).get("id") == "sys_lock"
    assert "actions" not in keys.get("0", {})


def test_clear_key(window):
    window._on_action_dropped(2, "sys_mute")
    window._on_key_clear(2)
    assert window.cfg["pages"][0]["keys"].get("2", {}) == {}


def test_add_and_delete_page(window):
    window._add_page()
    assert window._page_bar.count() == 2
    assert len(window.cfg["pages"]) == 2


def test_page_goto_param_is_dropdown(qapp):
    from streamdeck_controller.gui.key_panel import TriggerEditor
    editor = TriggerEditor("single", pages_provider=lambda: ["Hauptseite", "Musik", "System"])
    editor.load({"id": "page_goto", "params": {"page": 2}})
    value = editor.value()
    assert value["id"] == "page_goto"
    assert value["params"]["page"] == 2  # Dropdown hält die 1-basierte Auswahl

    combo = editor._steps[0]._param_edits["page"]
    assert combo.count() == 3
    combo.setCurrentIndex(2)
    assert editor.value()["params"]["page"] == 3


def test_action_chain_roundtrip(qapp):
    from streamdeck_controller.gui.key_panel import TriggerEditor
    editor = TriggerEditor("single")

    # Eine Aktion → dict (kompatibel zum alten Format)
    editor.load({"id": "sys_mute", "params": {}})
    assert editor.value() == {"id": "sys_mute", "params": {}}

    # Kette laden → Liste bleibt erhalten, Reihenfolge stimmt
    chain = [{"id": "sys_mute", "params": {}},
             {"id": "sys_lock", "params": {}},
             {"id": "sys_suspend", "params": {}}]
    editor.load(chain)
    assert editor.value() == chain
    assert len(editor._steps) == 3

    # Schritt entfernen → 2 Aktionen als Liste
    editor._remove_step(1)
    assert editor.value() == [{"id": "sys_mute", "params": {}},
                              {"id": "sys_suspend", "params": {}}]


def test_chain_executes_all_actions():
    from streamdeck_controller.daemon import DeckDaemon

    executed = []

    class _Exec:
        def execute(self, a):
            executed.append(a.get("id"))

    chain = [{"id": "sys_mute", "params": {}}, {"id": "sys_lock", "params": {}}]
    daemon = DeckDaemon.__new__(DeckDaemon)
    daemon.cfg = {"pages": [{"keys": {"0": {"actions": {"single": chain}}}}]}
    daemon.page = 0
    daemon.deck = None
    daemon.executor = _Exec()
    import threading
    daemon._lock = threading.RLock()
    daemon._toggle = {}

    daemon._fire(0, "single")
    import time
    time.sleep(0.2)  # Kette läuft im Thread
    assert executed == ["sys_mute", "sys_lock"]


def test_icon_packs_discovered():
    from streamdeck_controller.gui.icon_picker import discover_packs
    packs = discover_packs()
    assert "Standard" in packs
    assert len(packs["Standard"]) >= 40
    assert "Eigene" in packs  # lose Icons im icons/-Ordner
