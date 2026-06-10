"""Konfiguration: Defaults, Speichern/Laden, v1→v2-Migration."""

import json

import pytest

from streamdeck_controller import config as cfg_mod


@pytest.fixture(autouse=True)
def tmp_config(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setattr(cfg_mod, "CONFIG_PATH", path)
    return path


def test_default_config_when_missing():
    cfg = cfg_mod.load_config()
    assert cfg["version"] == 2
    assert cfg["pages"][0]["name"] == "Hauptseite"
    assert cfg["timing"]["hold_ms"] == 500


def test_save_and_load_roundtrip(tmp_config):
    cfg = cfg_mod.load_config()
    cfg["brightness"] = 42
    cfg_mod.save_config(cfg)
    assert cfg_mod.load_config()["brightness"] == 42
    assert tmp_config.exists()


def test_v1_migration(tmp_config):
    v1 = {
        "brightness": 70,
        "spotify_api": {"client_id": "abc123", "client_secret": "s3cret",
                        "redirect_uri": "http://localhost:8888/callback"},
        "pages": [{
            "name": "Hauptseite",
            "keys": {
                "0": {"label": "Play",
                      "icon": "~/icons/play.png",
                      "icon_active": "~/icons/play_a.png",
                      "single_press": {"type": "spotify_dbus", "command": "play_pause",
                                       "_fn_id": "spotify_play_pause"}},
                "1": {"label": "FF",
                      "single_press": {"type": "command", "cmd": "firefox",
                                       "_fn_id": "app_launch"}},
                "2": {"label": "S2",
                      "single_press": {"type": "page", "target": 1,
                                       "_fn_id": "page_switch"}},
            },
        }],
    }
    tmp_config.write_text(json.dumps(v1))

    cfg = cfg_mod.load_config()

    assert cfg["version"] == 2
    assert cfg["brightness"] == 70
    assert cfg["spotify"]["client_id"] == "abc123"

    keys = cfg["pages"][0]["keys"]
    assert keys["0"]["actions"]["single"]["id"] == "spotify_play_pause"
    assert keys["0"]["icon"] == "~/icons/play.png"
    assert keys["0"]["icon_active"] == "~/icons/play_a.png"
    assert keys["1"]["actions"]["single"] == {"id": "app_launch", "params": {"cmd": "firefox"}}
    assert keys["2"]["actions"]["single"]["id"] == "page_goto"
    assert keys["2"]["actions"]["single"]["params"]["page"] == 1

    # Backup der alten Datei wurde angelegt, Migration persistiert
    assert tmp_config.with_suffix(".json.v1-backup").exists()
    assert json.loads(tmp_config.read_text())["version"] == 2


def test_key_config_helpers():
    cfg = cfg_mod.load_config()
    cfg_mod.set_key_config(cfg, 0, 3, {"label": "X"})
    assert cfg_mod.get_key_config(cfg, 0, 3) == {"label": "X"}
    cfg_mod.set_key_config(cfg, 0, 3, {})
    assert cfg_mod.get_key_config(cfg, 0, 3) == {}
    # Seite, die noch nicht existiert, wird angelegt
    cfg_mod.set_key_config(cfg, 2, 0, {"label": "Neu"})
    assert len(cfg["pages"]) == 3
