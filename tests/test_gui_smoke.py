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
