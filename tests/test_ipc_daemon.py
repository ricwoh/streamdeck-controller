"""IPC-Server/Client und Daemon-Statuslogik (ohne Hardware)."""

import pytest

from streamdeck_controller import ipc as ipc_mod
from streamdeck_controller.ipc import IPCServer, ipc_request


@pytest.fixture
def socket_path(tmp_path, monkeypatch):
    path = tmp_path / "test.sock"
    monkeypatch.setattr(ipc_mod, "SOCKET_PATH", path)
    return path


def test_ipc_roundtrip(socket_path):
    server = IPCServer(lambda req: {"ok": True, "echo": req.get("cmd")})
    server.start()
    try:
        response = ipc_request({"cmd": "ping"})
        assert response == {"ok": True, "echo": "ping"}
    finally:
        server.stop()


def test_ipc_request_without_server(socket_path):
    assert ipc_request({"cmd": "ping"}) is None


def test_daemon_ipc_handler(tmp_path, monkeypatch):
    from streamdeck_controller import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "CONFIG_PATH", tmp_path / "config.json")
    from streamdeck_controller.daemon import DeckDaemon

    daemon = DeckDaemon.__new__(DeckDaemon)  # ohne __init__-Hardwareteile
    daemon.cfg = cfg_mod.load_config()
    daemon.page = 0
    daemon.deck = None
    daemon.deck_meta = {}

    class _Spotify:
        ready = False
    daemon.spotify = _Spotify()

    status = daemon._handle_ipc({"cmd": "status"})
    assert status["ok"] is True
    assert status["connected"] is False
    assert status["pages"] == ["Hauptseite"]

    assert daemon._handle_ipc({"cmd": "ping"})["ok"] is True
    assert daemon._handle_ipc({"cmd": "unsinn"})["ok"] is False
