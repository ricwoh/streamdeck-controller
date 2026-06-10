"""CLI: Hilfe und Befehlsübersicht."""

from streamdeck_controller.cli import HELP, main


def test_help_lists_all_commands():
    for command in ("run", "start", "stop", "restart", "status", "ui",
                    "devices", "log", "config", "spotify", "autostart", "version"):
        assert command in HELP, f"{command} fehlt in der Hilfe"


def test_no_args_shows_help(capsys):
    assert main([]) == 0
    assert "Verwendung: streamdeck" in capsys.readouterr().out


def test_unknown_command(capsys):
    assert main(["quatsch"]) == 2
    out = capsys.readouterr().out
    assert "Unbekannter Befehl" in out


def test_version(capsys):
    assert main(["version"]) == 0
    assert "streamdeck-controller" in capsys.readouterr().out


def test_status_without_daemon(capsys, monkeypatch):
    from streamdeck_controller import cli
    monkeypatch.setattr(cli, "ipc_request", lambda *a, **k: None)
    assert main(["status"]) == 1
    assert "läuft nicht" in capsys.readouterr().out
