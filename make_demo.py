#!/usr/bin/env python3
"""Generate docs/demo.gif — a tiny animated preview of the cuppa pet.

Renders the cup straight from cuppa.SPRITE (so the GIF always matches the real
tool) plus wiggling steam and a ticking "awake for" status line. Build-time
only; not part of the shipped tool. Requires Pillow.
"""
import os
from PIL import Image, ImageDraw, ImageFont

from cuppa import SPRITE

P = 14          # pixel block size
STEAM_ROWS = 3
BG = (26, 26, 26)
COLORS = {"L": (68, 68, 68), "W": (255, 255, 255), "S": (175, 135, 95)}
TAN = (215, 175, 135)
GREY = (150, 150, 150)
STEAM_SHADES = [(110, 110, 110), (150, 150, 150), (185, 185, 185)]  # top→bottom

def _font(size):
    for path in ("/System/Library/Fonts/Menlo.ttc",
                 "/System/Library/Fonts/Monaco.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


FONT = _font(14)
STATUS_SAMPLE = "caffeinated  •  awake for 0:00:09"
STATUS_W = FONT.getlength(STATUS_SAMPLE)

GRID_W = len(SPRITE[0])
GRID_H = len(SPRITE)
SIDE, TOP, GAP, TEXT_H, BOT = 28, 14, 16, 30, 18
# Width fits whichever is wider — the cup or the status line.
W = int(max(GRID_W * P, STATUS_W)) + 2 * SIDE
H = TOP + STEAM_ROWS * P + GRID_H * P + GAP + TEXT_H + BOT
CUP_X = (W - GRID_W * P) // 2
CUP_Y = TOP + STEAM_ROWS * P


def frame(i):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # Steam: two wisps that wiggle left/right as they rise.
    for left in (True, False):
        base_x = CUP_X + (int(GRID_W * 0.36) if left else int(GRID_W * 0.62)) * P
        for row in range(STEAM_ROWS):
            dx = (-3 if (i + row) % 2 else 3) + (-1 if left else 1) * 2
            x = base_x + dx
            y = TOP + row * P
            d.rectangle([x, y, x + P - 5, y + P - 5], fill=STEAM_SHADES[row])

    # Cup: one square per sprite pixel.
    for r, line in enumerate(SPRITE):
        for c, ch in enumerate(line):
            if ch == ".":
                continue
            x, y = CUP_X + c * P, CUP_Y + r * P
            d.rectangle([x, y, x + P - 1, y + P - 1], fill=COLORS[ch])

    # Status line, ticking up a few seconds.
    secs = i // 2
    head, tail = "caffeinated", f"  •  awake for 0:00:0{secs}"
    total = d.textlength(head, font=FONT) + d.textlength(tail, font=FONT)
    tx = (W - total) // 2
    ty = CUP_Y + GRID_H * P + GAP
    d.text((tx, ty), head, font=FONT, fill=TAN)
    d.text((tx + d.textlength(head, font=FONT), ty), tail, font=FONT, fill=GREY)
    return img


def main():
    frames = [frame(i) for i in range(16)]
    os.makedirs("docs", exist_ok=True)
    out = "docs/demo.gif"
    frames[0].save(out, save_all=True, append_images=frames[1:],
                   duration=130, loop=0, optimize=True, disposal=2)
    print(f"wrote {out}  ({W}x{H}, {len(frames)} frames, "
          f"{os.path.getsize(out) // 1024} KB)")


if __name__ == "__main__":
    main()
