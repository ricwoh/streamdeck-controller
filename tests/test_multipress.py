"""Multi-Press-Logik: 1×, 2×, Halten."""

import time

from streamdeck_controller.multipress import MultiPressRouter

WINDOW_MS = 80
HOLD_MS = 120


def make_router(triggers: dict[str, bool]):
    fired = []
    router = MultiPressRouter(
        fire=lambda key, trigger: fired.append(trigger),
        has_trigger=lambda key, trigger: triggers.get(trigger, False),
        double_window_ms=WINDOW_MS,
        hold_ms=HOLD_MS,
    )
    return router, fired


def click(router, key=0, duration=0.01):
    router.event(key, True)
    time.sleep(duration)
    router.event(key, False)


def wait():
    time.sleep((WINDOW_MS + HOLD_MS) / 1000 + 0.05)


def test_single_only_fires_immediately_on_press():
    router, fired = make_router({"single": True})
    router.event(0, True)
    assert fired == ["single"]  # ohne Verzögerung, schon beim Drücken
    router.event(0, False)
    wait()
    assert fired == ["single"]


def test_double_press_fires_double():
    router, fired = make_router({"single": True, "double": True})
    click(router)
    click(router)
    wait()
    assert fired == ["double"]


def test_single_with_double_configured_waits_window():
    router, fired = make_router({"single": True, "double": True})
    click(router)
    assert fired == []  # wartet auf möglichen zweiten Klick
    wait()
    assert fired == ["single"]


def test_hold_fires_while_held():
    router, fired = make_router({"single": True, "hold": True})
    router.event(0, True)
    time.sleep(HOLD_MS / 1000 + 0.05)
    assert fired == ["hold"]  # feuert bereits während des Haltens
    router.event(0, False)
    wait()
    assert fired == ["hold"]


def test_short_press_with_hold_configured_fires_single_on_release():
    router, fired = make_router({"single": True, "hold": True})
    click(router)
    assert fired == ["single"]
    wait()
    assert fired == ["single"]


def test_all_three_triggers():
    router, fired = make_router({"single": True, "double": True, "hold": True})

    click(router)            # einfacher Klick …
    wait()
    assert fired == ["single"]

    click(router)            # Doppelklick
    click(router)
    wait()
    assert fired == ["single", "double"]

    router.event(0, True)    # Halten
    time.sleep(HOLD_MS / 1000 + 0.05)
    router.event(0, False)
    wait()
    assert fired == ["single", "double", "hold"]


def test_reset_cancels_pending_timers():
    router, fired = make_router({"single": True, "double": True})
    click(router)             # wartet auf Doppelklick-Fenster …
    router.reset()            # … Seitenwechsel/Reload bricht Timer ab
    wait()
    assert fired == []        # kein verspätetes "single" nach dem Reset


def test_keys_are_independent():
    fired = []
    router = MultiPressRouter(
        fire=lambda key, trigger: fired.append((key, trigger)),
        has_trigger=lambda key, trigger: trigger == "single",
        double_window_ms=WINDOW_MS, hold_ms=HOLD_MS,
    )
    router.event(0, True)
    router.event(1, True)
    assert fired == [(0, "single"), (1, "single")]
