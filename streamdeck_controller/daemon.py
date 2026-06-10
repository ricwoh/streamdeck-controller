"""Headless-Daemon: verbindet das Stream Deck, rendert Tasten, führt Aktionen aus.

Läuft ohne GUI (z.B. als systemd-User-Service). Die GUI und die CLI sprechen
über den IPC-Socket mit ihm (reload, status, page, …).
"""

import logging
import signal
import threading
import time

from . import __version__
from .actions import ACTIONS_BY_ID, ActionExecutor
from .config import get_key_config, load_config
from .deck.manager import deck_info, find_deck
from .deck.renderer import render_key
from .ipc import IPCServer
from .multipress import MultiPressRouter
from .paths import CONFIG_PATH
from .spotify import SpotifyClient

log = logging.getLogger(__name__)

RECONNECT_INTERVAL = 3.0
NOW_PLAYING_INTERVAL = 5.0


class DeckDaemon:
    def __init__(self):
        self.cfg = load_config()
        self.page = 0
        self.deck = None
        self.deck_meta: dict = {}
        self._stop = threading.Event()
        self._toggle: dict[tuple[int, int], bool] = {}
        self._cover_cache: dict[str, bytes] = {}
        self._now_playing: dict | None = None
        self._lock = threading.RLock()
        self._config_mtime = self._mtime()

        self.spotify = self._make_spotify()
        self.executor = ActionExecutor(self)
        timing = self.cfg.get("timing", {})
        self.router = MultiPressRouter(
            fire=self._fire,
            has_trigger=self._has_trigger,
            double_window_ms=timing.get("double_window_ms", 300),
            hold_ms=timing.get("hold_ms", 500),
        )
        self.ipc = IPCServer(self._handle_ipc)

    # ── Hilfen ────────────────────────────────────────────────────────
    def _make_spotify(self) -> SpotifyClient:
        sp_cfg = self.cfg.get("spotify", {})
        return SpotifyClient(sp_cfg.get("client_id", ""))

    def _mtime(self) -> float:
        try:
            return CONFIG_PATH.stat().st_mtime
        except OSError:
            return 0.0

    def _current_page(self) -> dict:
        pages = self.cfg.get("pages", [{}])
        self.page = min(self.page, len(pages) - 1)
        return pages[self.page]

    def _key_action(self, key: int, trigger: str) -> dict | None:
        kc = get_key_config(self.cfg, self.page, key)
        return kc.get("actions", {}).get(trigger)

    def _has_trigger(self, key: int, trigger: str) -> bool:
        return self._key_action(key, trigger) is not None

    # ── Seiten (vom Executor genutzt) ─────────────────────────────────
    def goto_page(self, idx: int):
        with self._lock:
            pages = self.cfg.get("pages", [])
            if pages:
                self.page = max(0, min(idx, len(pages) - 1))
                self.router.reset()
                self.render_all()

    def next_page(self):
        self.goto_page((self.page + 1) % max(1, len(self.cfg.get("pages", []))))

    def prev_page(self):
        self.goto_page((self.page - 1) % max(1, len(self.cfg.get("pages", []))))

    # ── Tastendruck → Aktion ──────────────────────────────────────────
    def _fire(self, key: int, trigger: str):
        action = self._key_action(key, trigger)
        if not action:
            return
        spec = ACTIONS_BY_ID.get(action.get("id", ""))
        if spec and spec.toggle:
            with self._lock:
                state = self._toggle.get((self.page, key), False)
                self._toggle[(self.page, key)] = not state
            self.render_one(key)
        else:
            self._flash(key)
        threading.Thread(target=self.executor.execute, args=(action,),
                         daemon=True, name=f"action-{action.get('id')}").start()

    def _on_deck_event(self, _deck, key: int, pressed: bool):
        try:
            self.router.event(key, pressed)
        except Exception as e:
            log.error("Tasten-Event %s: %s", key, e)

    # ── Rendering ─────────────────────────────────────────────────────
    def render_all(self):
        deck = self.deck
        if not deck:
            return
        for i in range(self.deck_meta.get("keys", deck.key_count())):
            self.render_one(i)

    def render_one(self, key: int, flash: bool = False):
        deck = self.deck
        if not deck:
            return
        kc = get_key_config(self.cfg, self.page, key)
        active = self._toggle.get((self.page, key), False)
        icon = kc.get("icon_active" if active else "icon", "") or kc.get("icon", "")

        cover = None
        label = kc.get("label", "")
        if self._uses_now_playing(kc) and self._now_playing:
            np = self._now_playing
            if np.get("cover_url"):
                cover = self._cover_cache.get(np["cover_url"])
            if not label:
                label = np.get("title", "")
        try:
            with self._lock:
                deck.set_key_image(key, render_key(deck, icon, label,
                                                   flash=flash, cover=cover))
        except Exception as e:
            log.debug("Rendern Taste %d: %s", key, e)

    def _flash(self, key: int):
        self.render_one(key, flash=True)
        timer = threading.Timer(0.18, lambda: self.render_one(key))
        timer.daemon = True
        timer.start()

    @staticmethod
    def _uses_now_playing(kc: dict) -> bool:
        return any(a.get("id") == "spotify_now_playing"
                   for a in kc.get("actions", {}).values())

    def _page_has_now_playing(self) -> bool:
        page = self._current_page()
        return any(self._uses_now_playing(kc) for kc in page.get("keys", {}).values())

    # ── Now-Playing-Poller ────────────────────────────────────────────
    def _poll_now_playing(self):
        if not self.deck or not self._page_has_now_playing() or not self.spotify.ready:
            return
        np = self.spotify.now_playing()
        changed = np != self._now_playing
        self._now_playing = np
        if np and np.get("cover_url") and np["cover_url"] not in self._cover_cache:
            data = self.spotify.fetch_cover(np["cover_url"])
            if data:
                self._cover_cache[np["cover_url"]] = data
                if len(self._cover_cache) > 30:
                    self._cover_cache.pop(next(iter(self._cover_cache)))
        if changed:
            page = self._current_page()
            for key_str, kc in page.get("keys", {}).items():
                if self._uses_now_playing(kc):
                    self._toggle[(self.page, int(key_str))] = bool(np and np.get("is_playing"))
                    self.render_one(int(key_str))

    # ── Konfiguration neu laden ───────────────────────────────────────
    def reload_config(self):
        with self._lock:
            self.cfg = load_config()
            self.spotify = self._make_spotify()
            timing = self.cfg.get("timing", {})
            self.router.set_timing(timing.get("double_window_ms", 300),
                                   timing.get("hold_ms", 500))
            # Veraltete Zustände verwerfen (Belegung/Spotify können sich geändert haben)
            self._toggle.clear()
            self._now_playing = None
            self._config_mtime = self._mtime()
            if self.deck:
                try:
                    self.deck.set_brightness(self.cfg.get("brightness", 80))
                except Exception:
                    pass
            self.render_all()
        log.info("Konfiguration neu geladen.")

    # ── IPC ───────────────────────────────────────────────────────────
    def _handle_ipc(self, request: dict) -> dict:
        cmd = request.get("cmd", "")
        if cmd == "ping":
            return {"ok": True, "version": __version__}
        if cmd == "status":
            return {
                "ok": True,
                "version": __version__,
                "connected": self.deck is not None,
                "device": self.deck_meta,
                "page": self.page,
                "pages": [p.get("name", "") for p in self.cfg.get("pages", [])],
                "spotify_ready": self.spotify.ready,
            }
        if cmd == "reload":
            self.reload_config()
            return {"ok": True}
        if cmd == "page":
            self.goto_page(int(request.get("page", 0)))
            return {"ok": True, "page": self.page}
        if cmd == "stop":
            self._stop.set()
            return {"ok": True}
        return {"ok": False, "error": f"Unbekannter Befehl: {cmd}"}

    # ── Hauptschleife ─────────────────────────────────────────────────
    def run(self):
        log.info("Stream-Deck-Daemon %s startet…", __version__)
        self.ipc.start()
        signal.signal(signal.SIGTERM, lambda *_: self.stop())
        signal.signal(signal.SIGINT, lambda *_: self.stop())

        last_poll = 0.0
        try:
            while not self._stop.is_set():
                if self.deck is None:
                    self._try_connect()
                    if self.deck is None:
                        self._stop.wait(RECONNECT_INTERVAL)
                        continue

                if not self.deck.connected():
                    log.info("Deck getrennt.")
                    self._close_deck()
                    continue

                if self._mtime() != self._config_mtime:
                    self.reload_config()

                now = time.time()
                if now - last_poll >= NOW_PLAYING_INTERVAL:
                    last_poll = now
                    try:
                        self._poll_now_playing()
                    except Exception as e:
                        log.debug("Now-Playing-Poll: %s", e)

                self._stop.wait(0.25)
        finally:
            self._close_deck()
            self.ipc.stop()
            log.info("Daemon beendet.")

    def _try_connect(self):
        serial = self.cfg.get("device", {}).get("serial")
        deck = find_deck(serial)
        if deck is None:
            return
        try:
            deck.open()
            deck.reset()
            deck.set_brightness(self.cfg.get("brightness", 80))
            deck.set_key_callback(self._on_deck_event)
            self.deck = deck
            self.deck_meta = deck_info(deck, opened=True)
            self.router.reset()
            log.info("Deck verbunden: %s (%s Tasten, Serial %s)",
                     self.deck_meta.get("type"), self.deck_meta.get("keys"),
                     self.deck_meta.get("serial"))
            self.render_all()
        except Exception as e:
            log.warning("Deck-Verbindung fehlgeschlagen: %s", e)
            try:
                deck.close()
            except Exception:
                pass
            self.deck = None

    def _close_deck(self):
        if self.deck:
            try:
                self.deck.reset()
                self.deck.close()
            except Exception:
                pass
            self.deck = None

    def stop(self):
        self._stop.set()


def run_daemon():
    from .paths import LOG_PATH
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
    )
    DeckDaemon().run()
