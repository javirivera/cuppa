#!/usr/bin/env python3
"""
cuppa — run macOS `caffeinate` with a little animated cappuccino-cup pet.

While this runs, your Mac stays awake (caffeinate) and a little cup sips along
in the terminal with rising steam and an occasional blink. Ctrl+C to stop;
caffeinate is terminated cleanly so your Mac can sleep again.

Usage:
    ./cuppa.py                 # default: prevent idle sleep (caffeinate -i)
    ./cuppa.py -t 3600         # stay awake for 1 hour, then quit
    ./cuppa.py -- -d -s        # pass extra flags straight to caffeinate
"""

import argparse
import itertools
import shutil
import signal
import subprocess
import sys
import threading
import time

__version__ = "1.0.2"

# Set by _on_resize (SIGWINCH) so the next frame does a full clear. Without an
# alternate screen buffer, enlarging the terminal window can reveal rows that
# scrolled into history while it was smaller — rows still holding a stale
# earlier frame that per-line erase never touches. One full clear right after
# a resize wipes it.
resize_event = threading.Event()


def _on_resize(signum, frame):
    resize_event.set()

# ANSI helpers --------------------------------------------------------------
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
CLEAR_SCREEN = "\033[2J\033[H"  # full clear — used once at startup only
HOME = "\033[H"                # per-frame cursor reset (no full clear)
CLEAR_EOL = "\033[K"            # erase-to-end-of-line, wipes stale trailing chars
DIM = "\033[2m"
RESET = "\033[0m"
MARGIN = " "  # small left indent so the sprite isn't flush to the edge

# 256-colour palette.
WHITE = 231    # white paper cup body
LID = 238      # dark plastic lid
SLEEVE = 137   # kraft cardboard sleeve
CREMA = 180    # warm-tan accent (status line)
EYE = 16       # near-black eyes
STEAM_C = 250  # light-grey steam

# Pixel sprite of a tall paper to-go cup: a domed lid (flush with the body, no
# overhang), a mostly-straight white body that only narrows at the very base,
# and a kraft sleeve band. Each char is one pixel; rows are drawn two-at-a-time
# with half-block glyphs (see sprite_lines) so cells fill fully and there are
# no horizontal seams. An even row count keeps the pairing clean. Legend:
#   . transparent   L lid   W cup   S sleeve
SPRITE = [
    "..LLL..",
    ".LLLLL.",
    ".WWWWW.",
    ".WWWWW.",
    ".WWWWW.",
    ".WWWWW.",
    ".SSSSS.",
    ".SSSSS.",
    ".WWWWW.",
    ".WWWWW.",
    ".WWWWW.",
    ".WWWWW.",
    "..WWW..",
    "..WWW..",
]
PIXELS = {"L": LID, "W": WHITE, "S": SLEEVE}


def _pixel_color(ch, blink):
    """Map a sprite char to a colour code, or None for transparent."""
    if ch == ".":
        return None
    if ch == "E":
        return WHITE if blink else EYE  # eyes close into the cup on blink
    return PIXELS[ch]


def _halfcell(top, bot):
    """Two-wide half-block cell: upper half = top pixel, lower half = bottom.

    Solid cells (both halves the same) are painted as a background-coloured
    space — no glyph — so the whole cell fills with zero risk of the seam that
    block glyphs leave between rows. Only colour transitions use ▀ / ▄.
    """
    if top is None and bot is None:
        return "  "
    if top == bot:  # both same colour -> fill the cell via background
        return f"\033[48;5;{top}m  {RESET}"
    if top is not None and bot is not None:
        return f"\033[38;5;{top};48;5;{bot}m▀▀{RESET}"
    if top is not None:
        return f"\033[38;5;{top}m▀▀{RESET}"
    return f"\033[38;5;{bot}m▄▄{RESET}"


def sprite_lines(blink):
    """Render the sprite two rows per line with half-blocks (no row seams)."""
    rows = [[_pixel_color(ch, blink) for ch in row] for row in SPRITE]
    blank = [None] * len(rows[0])
    lines = []
    for i in range(0, len(rows), 2):
        top = rows[i]
        bot = rows[i + 1] if i + 1 < len(rows) else blank
        lines.append(MARGIN + "".join(_halfcell(t, b) for t, b in zip(top, bot)))
    return lines


# Steam wisps shimmer up over the bowl, across the 14-cell-wide sprite.
def _steam_line(marks):
    cells = [" "] * 14
    for col, glyph in marks.items():
        cells[col] = glyph
    return MARGIN + f"\033[38;5;{STEAM_C}m" + "".join(cells) + RESET


STEAM_FRAMES = [
    [_steam_line({5: "░", 8: "▒"}), _steam_line({6: "▒", 7: "░"}),
     _steam_line({5: "▒", 8: "░"})],
    [_steam_line({6: "▒", 7: "░"}), _steam_line({5: "░", 8: "▒"}),
     _steam_line({6: "░", 7: "▒"})],
    [_steam_line({5: "▒", 8: "░"}), _steam_line({6: "░", 7: "▒"}),
     _steam_line({5: "░", 8: "▒"})],
]


def cup(steam_frame, blink):
    """Full cuppa frame: steam wisps stacked above the cup sprite."""
    return list(steam_frame) + sprite_lines(blink)


def frame_output(frame_lines, status, force_clear=False):
    """Build one frame: cursor-home, then every line erased to EOL as it's
    rewritten. No full-screen clear here every frame — that's what caused the
    terminal's output queue to back up (and Ctrl+C to lag) at 4 frames/second.
    Erasing each line individually also wipes stale trailing characters, which
    matters for the status line: the `-t` countdown shrinks over time
    (`100s left` -> `9s left`), so without erase-to-EOL a leftover digit would
    linger. The leading blank line matches the original layout (row 1 stays
    empty; the cup starts on row 2).

    force_clear does one full CLEAR_SCREEN before drawing — used right after a
    terminal resize (see _on_resize) to wipe rows revealed from history.
    """
    lines = [""] + list(frame_lines) + [
        "",
        f"{DIM}{status}{RESET}",
        f"{DIM}Ctrl+C to let your Mac sleep again.{RESET}",
    ]
    prefix = CLEAR_SCREEN if force_clear else ""
    return prefix + HOME + "".join(line + CLEAR_EOL + "\n" for line in lines)


def render(frame_lines, status):
    force_clear = resize_event.is_set()
    if force_clear:
        resize_event.clear()
    sys.stdout.write(frame_output(frame_lines, status, force_clear))
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(
        description="cuppa — run caffeinate with an animated cappuccino-cup pet.",
        epilog="Anything after `--` is passed straight to caffeinate.",
    )
    parser.add_argument(
        "--version", action="version", version=f"cuppa {__version__}",
    )
    parser.add_argument(
        "-t", "--timeout", type=int, default=None,
        help="Seconds to stay awake before quitting (default: until Ctrl+C).",
    )
    parser.add_argument(
        "caffeinate_args", nargs=argparse.REMAINDER,
        help="Extra args for caffeinate (after --).",
    )
    args = parser.parse_args()

    if shutil.which("caffeinate") is None:
        sys.exit("error: `caffeinate` not found — this script is macOS-only.")

    # Build the caffeinate command. Default to idle-sleep prevention (-i); the
    # display may still sleep. -t makes caffeinate self-terminate after timeout.
    extra = [a for a in args.caffeinate_args if a != "--"]
    cmd = ["caffeinate"]
    if not extra:
        cmd += ["-i"]
    cmd += extra
    if args.timeout:
        cmd += ["-t", str(args.timeout)]

    proc = subprocess.Popen(cmd)
    start = time.monotonic()

    signal.signal(signal.SIGWINCH, _on_resize)
    sys.stdout.write(HIDE_CURSOR + CLEAR_SCREEN)
    try:
        steam = itertools.cycle(STEAM_FRAMES)
        tick = 0
        while proc.poll() is None:
            blink = (tick % 20) in (0, 1)  # quick blink every ~5s
            elapsed = int(time.monotonic() - start)
            mins, secs = divmod(elapsed, 60)
            hours, mins = divmod(mins, 60)
            awake = f"{hours:d}:{mins:02d}:{secs:02d}"
            status = f"\033[38;5;{CREMA}mcaffeinated{RESET}  •  awake for {awake}"
            if args.timeout:
                status += f"  •  {max(0, args.timeout - elapsed)}s left"
            render(cup(next(steam), blink), status)
            tick += 1
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        sys.stdout.write(SHOW_CURSOR + RESET + "\n")
        sys.stdout.flush()
        print("☕ cuppa napping — your Mac can sleep now.")


if __name__ == "__main__":
    main()
