"""Erkennung von Einfachdruck, Doppeldruck und Halten pro Taste.

Logik pro Taste (abhängig davon, welche Trigger belegt sind):

- Nur "single" belegt        → sofort beim Drücken auslösen (keine Verzögerung).
- "hold" belegt              → Timer beim Drücken; läuft er ab, während die Taste
                               noch gedrückt ist, feuert "hold". Loslassen vorher
                               zählt als (Teil eines) Klicks.
- "double" belegt            → nach dem ersten Klick wird kurz gewartet
                               (double_window); kommt ein zweiter Druck, feuert
                               "double", sonst "single".
"""

import threading
import time


class KeyPressTracker:
    """Verfolgt den Druckzustand einer einzelnen Taste."""

    def __init__(self, fire, has_trigger, double_window: float, hold_time: float):
        """
        fire(trigger: str)          — Callback zum Auslösen ("single"/"double"/"hold")
        has_trigger(trigger) -> bool — ist der Trigger auf dieser Taste belegt?
        """
        self._fire = fire
        self._has = has_trigger
        self._double_window = double_window
        self._hold_time = hold_time
        self._lock = threading.Lock()
        self._pressed = False
        self._hold_fired = False
        self._click_count = 0
        self._hold_timer: threading.Timer | None = None
        self._single_timer: threading.Timer | None = None

    def cancel(self):
        """Alle laufenden Timer abbrechen (z.B. bei Seitenwechsel/Reload)."""
        with self._lock:
            if self._hold_timer:
                self._hold_timer.cancel()
                self._hold_timer = None
            if self._single_timer:
                self._single_timer.cancel()
                self._single_timer = None
            self._pressed = False
            self._hold_fired = False
            self._click_count = 0

    def press(self):
        with self._lock:
            self._pressed = True
            self._hold_fired = False
            if self._single_timer:
                # zweiter Druck innerhalb des Doppelklick-Fensters
                self._single_timer.cancel()
                self._single_timer = None
                self._click_count = 1
            else:
                self._click_count = 0

            if not self._has("double") and not self._has("hold"):
                # schnellster Fall: sofort feuern
                self._fire("single")
                self._click_count = -1  # Release ignorieren
                return

            if self._has("hold"):
                self._hold_timer = threading.Timer(self._hold_time, self._on_hold)
                self._hold_timer.daemon = True
                self._hold_timer.start()

    def release(self):
        with self._lock:
            if not self._pressed:
                # Release ohne zugehöriges Press (z.B. nach reset() durch
                # Seitenwechsel, während die Taste noch gehalten wurde) —
                # sonst feuert die Belegung der NEUEN Seite beim Loslassen.
                return
            self._pressed = False
            if self._hold_timer:
                self._hold_timer.cancel()
                self._hold_timer = None
            if self._click_count == -1:
                self._click_count = 0
                return
            if self._hold_fired:
                self._hold_fired = False
                self._click_count = 0
                return

            if self._click_count >= 1 and self._has("double"):
                # zweiter abgeschlossener Klick → Doppeldruck
                self._click_count = 0
                self._fire("double")
                return

            if not self._has("double"):
                # kein Doppeldruck konfiguriert → single direkt beim Loslassen
                self._fire("single")
                return

            # auf möglichen zweiten Klick warten
            self._single_timer = threading.Timer(self._double_window, self._on_single_timeout)
            self._single_timer.daemon = True
            self._single_timer.start()

    def _on_hold(self):
        with self._lock:
            if self._pressed:
                self._hold_fired = True
                self._fire("hold")

    def _on_single_timeout(self):
        with self._lock:
            self._single_timer = None
            self._click_count = 0
            self._fire("single")


class MultiPressRouter:
    """Verwaltet KeyPressTracker für alle Tasten eines Decks."""

    def __init__(self, fire, has_trigger,
                 double_window_ms: int = 300, hold_ms: int = 500):
        """
        fire(key: int, trigger: str)
        has_trigger(key: int, trigger: str) -> bool
        """
        self._fire = fire
        self._has = has_trigger
        self._double_window = double_window_ms / 1000.0
        self._hold_time = hold_ms / 1000.0
        self._trackers: dict[int, KeyPressTracker] = {}

    def set_timing(self, double_window_ms: int, hold_ms: int):
        self._double_window = double_window_ms / 1000.0
        self._hold_time = hold_ms / 1000.0
        self.reset()

    def reset(self):
        for tracker in self._trackers.values():
            tracker.cancel()
        self._trackers.clear()

    def _tracker(self, key: int) -> KeyPressTracker:
        if key not in self._trackers:
            self._trackers[key] = KeyPressTracker(
                fire=lambda trigger, k=key: self._fire(k, trigger),
                has_trigger=lambda trigger, k=key: self._has(k, trigger),
                double_window=self._double_window,
                hold_time=self._hold_time,
            )
        return self._trackers[key]

    def event(self, key: int, pressed: bool):
        tracker = self._tracker(key)
        if pressed:
            tracker.press()
        else:
            tracker.release()
