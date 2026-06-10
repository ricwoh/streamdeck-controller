"""Konfiguration laden/speichern + Migration vom alten v1-Format."""

import json
import logging
from copy import deepcopy

from .paths import CONFIG_PATH

log = logging.getLogger(__name__)

CONFIG_VERSION = 2

DEFAULT_CONFIG = {
    "version": CONFIG_VERSION,
    "brightness": 80,
    "device": {"serial": None},
    "spotify": {
        "client_id": "",
        "client_secret": "",
        "redirect_uri": "http://127.0.0.1:8888/callback",
    },
    "timing": {"double_window_ms": 300, "hold_ms": 500},
    "pages": [{"name": "Hauptseite", "keys": {}}],
}

# Mapping alter _fn_id-Werte (v1) auf neue Aktions-IDs
_V1_FN_MAP = {
    "spotify_play_pause": "spotify_play_pause",
    "spotify_next": "spotify_next",
    "spotify_prev": "spotify_prev",
    "spotify_vol_up": "spotify_vol_up",
    "spotify_vol_down": "spotify_vol_down",
    "spotify_open": "app_launch",
    "spotify_song_info": "spotify_song_info",
    "sys_vol_up": "sys_vol_up",
    "sys_vol_down": "sys_vol_down",
    "sys_mute": "sys_mute",
    "sys_mic_mute": "sys_mic_mute",
    "sys_screenshot": "sys_screenshot",
    "sys_lock": "sys_lock",
    "sys_suspend": "sys_suspend",
    "sys_brightness_up": "sys_brightness_up",
    "sys_brightness_down": "sys_brightness_down",
    "app_launch": "app_launch",
    "open_url": "open_url",
    "open_folder": "open_folder",
    "page_switch": "page_goto",
    "custom_cmd": "custom_cmd",
}


def _migrate_v1(old: dict) -> dict:
    """Altes config.json (streamdeck_app.py) ins v2-Format überführen."""
    cfg = deepcopy(DEFAULT_CONFIG)
    cfg["brightness"] = old.get("brightness", 80)

    old_spotify = old.get("spotify_api", {})
    cfg["spotify"]["client_id"] = old_spotify.get("client_id", "")
    cfg["spotify"]["client_secret"] = old_spotify.get("client_secret", "")

    pages = []
    for old_page in old.get("pages", []):
        page = {"name": old_page.get("name", f"Seite {len(pages)}"), "keys": {}}
        for key, kc in old_page.get("keys", {}).items():
            new_kc = {"label": kc.get("label", "")}
            if kc.get("icon"):
                new_kc["icon"] = kc["icon"]
            if kc.get("icon_active"):
                new_kc["icon_active"] = kc["icon_active"]
            action = kc.get("single_press")
            if action:
                fn_id = _V1_FN_MAP.get(action.get("_fn_id", ""), "custom_cmd")
                params = {}
                if fn_id == "page_goto":
                    # v1 war 0-basiert, v2 ist 1-basiert
                    params["page"] = int(action.get("target", 0)) + 1
                elif action.get("_fn_id") == "spotify_open":
                    params["cmd"] = "spotify"
                elif "cmd" in action and action["cmd"]:
                    if fn_id == "open_url":
                        params["url"] = action["cmd"].removeprefix("xdg-open ").strip()
                    elif fn_id == "open_folder":
                        params["path"] = action["cmd"].removeprefix("xdg-open ").strip()
                    elif fn_id in ("app_launch", "custom_cmd"):
                        params["cmd"] = action["cmd"]
                new_kc["actions"] = {"single": {"id": fn_id, "params": params}}
            page["keys"][key] = new_kc
        pages.append(page)
    if pages:
        cfg["pages"] = pages
    log.info("Konfiguration von v1 nach v2 migriert (%d Seiten)", len(cfg["pages"]))
    return cfg


def _ensure_defaults(cfg: dict) -> dict:
    for key, val in DEFAULT_CONFIG.items():
        if key not in cfg:
            cfg[key] = deepcopy(val)
        elif isinstance(val, dict):
            for k2, v2 in val.items():
                cfg[key].setdefault(k2, deepcopy(v2))
    if not cfg.get("pages"):
        cfg["pages"] = deepcopy(DEFAULT_CONFIG["pages"])
    return cfg


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                cfg = json.load(f)
        except Exception as e:
            log.error("config.json nicht lesbar (%s) — Standardwerte werden genutzt", e)
            return deepcopy(DEFAULT_CONFIG)
        if cfg.get("version", 1) < 2:
            backup = CONFIG_PATH.with_suffix(".json.v1-backup")
            try:
                backup.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
                log.info("Backup der alten Konfiguration: %s", backup)
            except Exception:
                pass
            cfg = _migrate_v1(cfg)
            save_config(cfg)
        return _ensure_defaults(cfg)
    return deepcopy(DEFAULT_CONFIG)


def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    tmp.replace(CONFIG_PATH)


def get_key_config(cfg: dict, page_idx: int, key_idx: int) -> dict:
    pages = cfg.get("pages", [])
    if page_idx >= len(pages):
        return {}
    return pages[page_idx].get("keys", {}).get(str(key_idx), {})


def set_key_config(cfg: dict, page_idx: int, key_idx: int, key_cfg: dict):
    pages = cfg.setdefault("pages", [])
    while len(pages) <= page_idx:
        pages.append({"name": f"Seite {len(pages) + 1}", "keys": {}})
    keys = pages[page_idx].setdefault("keys", {})
    if key_cfg:
        keys[str(key_idx)] = key_cfg
    else:
        keys.pop(str(key_idx), None)
