"""Tastenbilder rendern (immer über PILHelper — nie manuell rotieren/flippen)."""

import io
import logging

from PIL import Image, ImageDraw, ImageEnhance, ImageFont
from StreamDeck.ImageHelpers import PILHelper

from ..paths import find_font, resolve_icon

log = logging.getLogger(__name__)

_FONT_PATH = find_font()


def _font(size: int):
    if _FONT_PATH:
        try:
            return ImageFont.truetype(_FONT_PATH, size)
        except Exception:
            pass
    return ImageFont.load_default()


def render_key(deck, icon_ref: str = "", label: str = "",
               flash: bool = False, cover: bytes | None = None,
               bg=(20, 20, 28), fg=(255, 255, 255)) -> bytes:
    """Fertiges Tastenbild im nativen Deck-Format erzeugen."""
    img = PILHelper.create_key_image(deck, background=bg)
    w, h = img.size

    layer = None
    if cover:
        try:
            layer = Image.open(io.BytesIO(cover)).convert("RGBA").resize((w, h), Image.LANCZOS)
        except Exception:
            layer = None
    if layer is None and icon_ref:
        path = resolve_icon(icon_ref)
        if path:
            try:
                layer = Image.open(path).convert("RGBA").resize((w, h), Image.LANCZOS)
            except Exception as e:
                log.debug("Icon %s nicht ladbar: %s", path, e)

    if layer is not None:
        if flash:
            layer = ImageEnhance.Brightness(layer).enhance(2.2)
        img.paste(layer, (0, 0), layer)
    elif flash:
        img = Image.new("RGB", (w, h), (90, 90, 130))

    if label:
        draw = ImageDraw.Draw(img)
        font = _font(max(11, h // 6))
        text = label if len(label) <= 12 else label[:11] + "…"
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        tx = max(0, (w - tw) // 2)
        ty = h - bbox[3] - 4
        draw.text((tx + 1, ty + 1), text, fill=(0, 0, 0), font=font)
        draw.text((tx, ty), text, fill=fg, font=font)

    return PILHelper.to_native_key_format(deck, img)


def render_blank(deck, bg=(0, 0, 0)) -> bytes:
    return PILHelper.to_native_key_format(deck, PILHelper.create_key_image(deck, background=bg))
