"""Stream-Deck-Erkennung und -Auswahl."""

import logging

from StreamDeck.DeviceManager import DeviceManager

log = logging.getLogger(__name__)


def enumerate_decks() -> list:
    try:
        return DeviceManager().enumerate()
    except Exception as e:
        log.error("Geräte-Suche fehlgeschlagen: %s", e)
        return []


def deck_info(deck, opened: bool = False) -> dict:
    """Geräteinfos lesen; öffnet das Deck kurz, falls nötig."""
    info = {"type": "?", "serial": None, "keys": 0, "cols": 0, "rows": 0}
    needs_close = False
    try:
        if not opened:
            deck.open()
            needs_close = True
        info["type"] = deck.deck_type()
        info["keys"] = deck.key_count()
        layout = deck.key_layout()  # (rows, cols)
        info["rows"], info["cols"] = layout[0], layout[1]
        try:
            info["serial"] = deck.get_serial_number()
        except Exception:
            pass
    except Exception as e:
        log.warning("Geräteinfo nicht lesbar: %s", e)
    finally:
        if needs_close:
            try:
                deck.close()
            except Exception:
                pass
    return info


def list_devices_info() -> list[dict]:
    return [deck_info(d) for d in enumerate_decks()]


def find_deck(serial: str | None = None):
    """Deck nach Seriennummer wählen; ohne Angabe das erste gefundene."""
    decks = enumerate_decks()
    if not decks:
        return None
    if not serial:
        return decks[0]
    for d in decks:
        try:
            d.open()
            s = d.get_serial_number()
            d.close()
        except Exception:
            continue
        if s == serial:
            return d
    return decks[0]
