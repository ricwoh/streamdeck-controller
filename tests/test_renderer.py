"""Tastenbild-Rendering mit einem Fake-Deck (Stream Deck Mini Format)."""

import io

from PIL import Image

from streamdeck_controller.deck.renderer import render_key, render_blank


class FakeMiniDeck:
    """Bildformat des Stream Deck Mini (laut Projekt-Notizen)."""

    def key_image_format(self):
        return {
            "size": (80, 80),
            "format": "BMP",
            "flip": (False, True),
            "rotation": 90,
        }


def _assert_bmp_80(data: bytes):
    assert isinstance(data, (bytes, bytearray)) and len(data) > 0
    img = Image.open(io.BytesIO(data))
    assert img.format == "BMP"
    assert img.size == (80, 80)


def test_render_blank():
    _assert_bmp_80(render_blank(FakeMiniDeck()))


def test_render_label_only():
    _assert_bmp_80(render_key(FakeMiniDeck(), label="Play"))


def test_render_builtin_icon_with_label_and_flash():
    _assert_bmp_80(render_key(FakeMiniDeck(), icon_ref="builtin:spotify_play_pause",
                              label="Play", flash=True))


def test_render_missing_icon_falls_back():
    _assert_bmp_80(render_key(FakeMiniDeck(), icon_ref="builtin:gibt_es_nicht", label="X"))


def test_render_cover_bytes():
    cover = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 30, 30)).save(cover, "PNG")
    _assert_bmp_80(render_key(FakeMiniDeck(), cover=cover.getvalue(), label="Song"))
