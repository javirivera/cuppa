#!/usr/bin/env python3
"""Tests for cuppa's render path — guards against the full-screen-clear regression
that caused per-frame terminal lag (and unresponsive Ctrl+C)."""

import contextlib
import io
import unittest

import cuppa


class FrameOutputTests(unittest.TestCase):
    def _status(self):
        return "caffeinated  •  awake for 0:00:00"

    def _frame(self):
        return cuppa.frame_output(
            cuppa.cup(cuppa.STEAM_FRAMES[0], blink=False), self._status()
        )

    def test_does_not_clear_the_whole_screen_per_frame(self):
        # A full-screen clear every frame is what floods the terminal's output
        # queue and delays Ctrl+C — the screen is cleared once at startup only.
        self.assertNotIn(cuppa.CLEAR_SCREEN, self._frame())

    def test_moves_cursor_home(self):
        self.assertIn(cuppa.HOME, self._frame())

    def test_erases_each_line_to_end_of_line(self):
        self.assertIn(cuppa.CLEAR_EOL, self._frame())

    def test_status_line_is_erased_to_end_of_line(self):
        # The countdown (`Ns left`) shrinks as time passes, so the status line
        # must be wiped to EOL each frame or a stale trailing digit lingers.
        status = self._status()
        frame = cuppa.frame_output(cuppa.cup(cuppa.STEAM_FRAMES[0], blink=False), status)
        self.assertIn(f"{status}{cuppa.RESET}{cuppa.CLEAR_EOL}", frame)

    def test_force_clear_prepends_a_full_screen_clear(self):
        # Growing the terminal window can reveal rows that scrolled into
        # history while it was smaller, still holding a stale earlier frame.
        # force_clear wipes that before drawing the new frame.
        frame = cuppa.frame_output(self._frame_lines(), self._status(), force_clear=True)
        self.assertTrue(frame.startswith(cuppa.CLEAR_SCREEN))

    def test_no_force_clear_by_default(self):
        self.assertNotIn(cuppa.CLEAR_SCREEN, self._frame())

    def _frame_lines(self):
        return cuppa.cup(cuppa.STEAM_FRAMES[0], blink=False)


class ResizeHandlingTests(unittest.TestCase):
    def tearDown(self):
        cuppa.resize_event.clear()

    def test_sigwinch_handler_marks_resize_pending(self):
        cuppa.resize_event.clear()
        cuppa._on_resize(None, None)
        self.assertTrue(cuppa.resize_event.is_set())

    def test_render_does_a_full_clear_once_after_a_resize(self):
        cuppa.resize_event.set()
        first = io.StringIO()
        with contextlib.redirect_stdout(first):
            cuppa.render(cuppa.cup(cuppa.STEAM_FRAMES[0], False), "status")
        self.assertIn(cuppa.CLEAR_SCREEN, first.getvalue())
        self.assertFalse(cuppa.resize_event.is_set())

        second = io.StringIO()
        with contextlib.redirect_stdout(second):
            cuppa.render(cuppa.cup(cuppa.STEAM_FRAMES[0], False), "status")
        self.assertNotIn(cuppa.CLEAR_SCREEN, second.getvalue())


if __name__ == "__main__":
    unittest.main()
