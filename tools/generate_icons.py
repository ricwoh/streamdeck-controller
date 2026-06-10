#!/usr/bin/env python3
"""Erzeugt die mitgelieferten Tastengrafiken (normal + aktiv) nach icons/builtin/.

Aufruf:  python3 tools/generate_icons.py
"""

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "icons" / "builtin"
SIZE = 256
C = SIZE / 2

NORMAL = (216, 222, 233, 255)
ACTIVE_SPOTIFY = (30, 215, 96, 255)
ACTIVE_DEFAULT = (137, 180, 250, 255)
RED = (243, 139, 168, 255)
W = 16  # Standard-Linienbreite


def canvas():
    return Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))


def _arrow_head(d, tip, angle, size, color):
    a1, a2 = angle + math.radians(150), angle - math.radians(150)
    p1 = (tip[0] + size * math.cos(a1), tip[1] + size * math.sin(a1))
    p2 = (tip[0] + size * math.cos(a2), tip[1] + size * math.sin(a2))
    d.polygon([tip, p1, p2], fill=color)


# ── Glyphen ────────────────────────────────────────────────────────────

def play(d, col):
    d.polygon([(90, 64), (90, 192), (190, 128)], fill=col)


def pause(d, col):
    d.rounded_rectangle([84, 64, 116, 192], 10, fill=col)
    d.rounded_rectangle([140, 64, 172, 192], 10, fill=col)


def next_track(d, col):
    d.polygon([(58, 72), (58, 184), (140, 128)], fill=col)
    d.polygon([(124, 72), (124, 184), (206, 128)], fill=col)
    d.rounded_rectangle([192, 72, 210, 184], 6, fill=col)


def prev_track(d, col):
    d.polygon([(198, 72), (198, 184), (116, 128)], fill=col)
    d.polygon([(132, 72), (132, 184), (50, 128)], fill=col)
    d.rounded_rectangle([46, 72, 64, 184], 6, fill=col)


def heart(d, col, filled):
    path = []
    for t in range(0, 360, 4):
        rad = math.radians(t)
        x = 16 * math.sin(rad) ** 3
        y = 13 * math.cos(rad) - 5 * math.cos(2 * rad) - 2 * math.cos(3 * rad) - math.cos(4 * rad)
        path.append((C + x * 6.4, C - y * 6.4 + 8))
    if filled:
        d.polygon(path, fill=col)
    else:
        d.line(path + [path[0]], fill=col, width=W, joint="curve")


def shuffle(d, col):
    d.line([(48, 88), (96, 88), (160, 168), (200, 168)], fill=col, width=W, joint="curve")
    d.line([(48, 168), (96, 168), (160, 88), (200, 88)], fill=col, width=W, joint="curve")
    _arrow_head(d, (216, 88), 0, 26, col)
    _arrow_head(d, (216, 168), 0, 26, col)


def speaker(d, col):
    d.polygon([(56, 104), (92, 104), (132, 68), (132, 188), (92, 152), (56, 152)], fill=col)


def vol_up(d, col):
    speaker(d, col)
    d.line([(168, 100), (168, 156)], fill=col, width=W)
    d.line([(140, 128), (196, 128)], fill=col, width=W)


def vol_down(d, col):
    speaker(d, col)
    d.line([(144, 128), (200, 128)], fill=col, width=W)


def mute(d, col, slash):
    speaker(d, col)
    if slash:
        d.line([(150, 100), (206, 156)], fill=col, width=W)
        d.line([(206, 100), (150, 156)], fill=col, width=W)
    else:
        d.arc([140, 96, 204, 160], -60, 60, fill=col, width=W)


def mic(d, col, slash):
    d.rounded_rectangle([104, 52, 152, 140], 24, fill=col)
    d.arc([84, 92, 172, 168], 0, 180, fill=col, width=W)
    d.line([(128, 168), (128, 196)], fill=col, width=W)
    d.line([(96, 200), (160, 200)], fill=col, width=W)
    if slash:
        d.line([(64, 48), (192, 208)], fill=RED, width=W + 4)


def brightness(d, col, plus):
    dark = (30, 30, 46, 255)
    d.ellipse([92, 92, 164, 164], fill=col)
    for i in range(8):
        ang = math.radians(i * 45)
        x1, y1 = C + 52 * math.cos(ang), C + 52 * math.sin(ang)
        x2, y2 = C + 76 * math.cos(ang), C + 76 * math.sin(ang)
        d.line([(x1, y1), (x2, y2)], fill=col, width=12)
    d.line([(110, 128), (146, 128)], fill=dark, width=14)
    if plus:
        d.line([(128, 110), (128, 146)], fill=dark, width=14)


def camera(d, col):
    d.rounded_rectangle([48, 84, 208, 188], 16, outline=col, width=W)
    d.rectangle([96, 64, 160, 88], fill=col)
    d.ellipse([100, 108, 156, 164], outline=col, width=W)


def lock(d, col):
    d.rounded_rectangle([72, 116, 184, 200], 14, fill=col)
    d.arc([92, 56, 164, 140], 180, 360, fill=col, width=W + 4)


def moon(d, col):
    d.ellipse([56, 56, 200, 200], fill=col)
    d.ellipse([88, 40, 232, 184], fill=(0, 0, 0, 0))


def power(d, col):
    d.arc([64, 72, 192, 200], -60, 240, fill=col, width=W + 2)
    d.line([(128, 48), (128, 128)], fill=col, width=W + 2)


def reboot(d, col):
    d.arc([64, 64, 192, 192], 30, 300, fill=col, width=W)
    # Pfeilspitze ans Bogen-Ende (300°)
    ang = math.radians(300)
    tip = (C + 64 * math.cos(ang), C + 64 * math.sin(ang))
    _arrow_head(d, tip, ang + math.radians(90), 34, col)


def playlist(d, col):
    for y in (76, 116, 156):
        d.line([(56, y), (150, y)], fill=col, width=W)
    d.line([(56, 196), (110, 196)], fill=col, width=W)
    d.polygon([(170, 140), (170, 212), (216, 176)], fill=col)


def device(d, col):
    d.rounded_rectangle([48, 64, 208, 164], 10, outline=col, width=W)
    d.line([(96, 196), (160, 196)], fill=col, width=W)
    d.line([(128, 164), (128, 196)], fill=col, width=W)


def note(d, col):
    d.ellipse([72, 156, 124, 200], fill=col)
    d.line([(118, 178), (118, 64)], fill=col, width=14)
    d.line([(118, 64), (188, 84)], fill=col, width=14)
    d.line([(182, 84), (182, 150)], fill=col, width=14)
    d.ellipse([140, 134, 188, 172], fill=col)


def info(d, col):
    d.ellipse([56, 56, 200, 200], outline=col, width=W)
    d.ellipse([118, 88, 138, 108], fill=col)
    d.line([(128, 124), (128, 168)], fill=col, width=W)


def window_icon(d, col):
    d.rounded_rectangle([48, 60, 208, 196], 12, outline=col, width=W)
    d.line([(48, 96), (208, 96)], fill=col, width=W)
    d.ellipse([64, 72, 80, 88], fill=col)


def globe(d, col):
    d.ellipse([56, 56, 200, 200], outline=col, width=W)
    d.ellipse([96, 56, 160, 200], outline=col, width=12)
    d.line([(56, 128), (200, 128)], fill=col, width=12)


def folder(d, col):
    d.polygon([(48, 84), (104, 84), (120, 104), (208, 104), (208, 188), (48, 188)], fill=col)


def chevron(d, col, direction):
    if direction > 0:
        d.line([(96, 64), (168, 128), (96, 192)], fill=col, width=W + 6, joint="curve")
    else:
        d.line([(160, 64), (88, 128), (160, 192)], fill=col, width=W + 6, joint="curve")


def pages_grid(d, col):
    for x, y in [(60, 60), (140, 60), (60, 140), (140, 140)]:
        d.rounded_rectangle([x, y, x + 56, y + 56], 8, outline=col, width=12)


def terminal(d, col):
    d.rounded_rectangle([40, 64, 216, 192], 12, outline=col, width=W)
    d.line([(68, 104), (104, 128), (68, 152)], fill=col, width=12, joint="curve")
    d.line([(120, 156), (176, 156)], fill=col, width=12)


# (name, zeichnen(d, col), aktiv-variante oder None, aktiv-farbe)
ICONS = {
    "spotify_play_pause": (play, pause, ACTIVE_SPOTIFY),
    "spotify_next": (next_track, None, ACTIVE_SPOTIFY),
    "spotify_prev": (prev_track, None, ACTIVE_SPOTIFY),
    "spotify_like": (lambda d, c: heart(d, c, False), lambda d, c: heart(d, c, True), ACTIVE_SPOTIFY),
    "spotify_shuffle": (shuffle, None, ACTIVE_SPOTIFY),
    "spotify_vol_up": (vol_up, None, ACTIVE_SPOTIFY),
    "spotify_vol_down": (vol_down, None, ACTIVE_SPOTIFY),
    "spotify_playlist": (playlist, None, ACTIVE_SPOTIFY),
    "spotify_device": (device, None, ACTIVE_SPOTIFY),
    "spotify_now_playing": (note, None, ACTIVE_SPOTIFY),
    "spotify_song_info": (info, None, ACTIVE_SPOTIFY),
    "sys_vol_up": (vol_up, None, ACTIVE_DEFAULT),
    "sys_vol_down": (vol_down, None, ACTIVE_DEFAULT),
    "sys_mute": (lambda d, c: mute(d, c, False), lambda d, c: mute(d, RED, True), ACTIVE_DEFAULT),
    "sys_mic_mute": (lambda d, c: mic(d, c, False), lambda d, c: mic(d, c, True), ACTIVE_DEFAULT),
    "sys_brightness_up": (lambda d, c: brightness(d, c, True), None, ACTIVE_DEFAULT),
    "sys_brightness_down": (lambda d, c: brightness(d, c, False), None, ACTIVE_DEFAULT),
    "sys_screenshot": (camera, None, ACTIVE_DEFAULT),
    "sys_lock": (lock, None, ACTIVE_DEFAULT),
    "sys_suspend": (moon, None, ACTIVE_DEFAULT),
    "sys_poweroff": (power, None, ACTIVE_DEFAULT),
    "sys_reboot": (reboot, None, ACTIVE_DEFAULT),
    "app_launch": (window_icon, None, ACTIVE_DEFAULT),
    "open_url": (globe, None, ACTIVE_DEFAULT),
    "open_folder": (folder, None, ACTIVE_DEFAULT),
    "page_next": (lambda d, c: chevron(d, c, +1), None, ACTIVE_DEFAULT),
    "page_prev": (lambda d, c: chevron(d, c, -1), None, ACTIVE_DEFAULT),
    "page_goto": (pages_grid, None, ACTIVE_DEFAULT),
    "custom_cmd": (terminal, None, ACTIVE_DEFAULT),
}


def render(draw_fn, color) -> Image.Image:
    img = canvas()
    draw_fn(ImageDraw.Draw(img), color)
    return img


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (normal_fn, active_fn, active_color) in ICONS.items():
        render(normal_fn, NORMAL).save(OUT / f"{name}.png")
        active_draw = active_fn or normal_fn
        render(active_draw, active_color).save(OUT / f"{name}_active.png")
    print(f"{len(ICONS) * 2} Icons nach {OUT} geschrieben.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
