"""
Player module — simulate swipe gestures on the iPhone Mirroring window.
Uses low-level Quartz CGEvents (kCGEventLeftMouseDragged) since pyautogui's
moveTo sends kCGEventMouseMoved which iPhone Mirroring ignores during drags.
"""
import time
import logging
import threading
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

try:
    import Quartz
    from Quartz import (
        CGEventCreateMouseEvent,
        CGEventPost,
        kCGEventLeftMouseDown,
        kCGEventLeftMouseUp,
        kCGEventLeftMouseDragged,
        kCGMouseButtonLeft,
        kCGHIDEventTap,
    )
    QUARTZ_AVAILABLE = True
except ImportError:
    QUARTZ_AVAILABLE = False



TILE_HOLD = 0.025
WORD_DELAY = 0.18
PRE_SWIPE_HOLD = 0.04


def _cg_point(x, y):
    return Quartz.CGPointMake(float(x), float(y))


def _post_mouse_event(event_type, x, y):
    event = CGEventCreateMouseEvent(None, event_type, _cg_point(x, y), kCGMouseButtonLeft)
    CGEventPost(kCGHIDEventTap, event)


def focus_window(
    grid_region: Tuple[int, int, int, int],
    window_offset: Tuple[int, int],
    scale: float,
):
    """Click the first grid tile to focus the window. The first word will re-click this tile anyway."""
    x, y = tile_to_screen(0, 0, grid_region, window_offset, scale)
    _post_mouse_event(kCGEventLeftMouseDown, x, y)
    time.sleep(0.02)
    _post_mouse_event(kCGEventLeftMouseUp, x, y)
    time.sleep(0.4)


def tile_to_screen(
    row: int, col: int,
    grid_region: Tuple[int, int, int, int],
    window_offset: Tuple[int, int] = (0, 0),
    scale: float = 1.0,
) -> Tuple[int, int]:
    gx, gy, gw, gh = grid_region
    wx, wy = window_offset

    cell_w = gw / 4
    cell_h = gh / 4

    x = wx + (gx + col * cell_w + cell_w / 2) / scale
    y = wy + (gy + row * cell_h + cell_h / 2) / scale

    return int(x), int(y)


def swipe_word(
    path: List[Tuple[int, int]],
    grid_region: Tuple[int, int, int, int],
    window_offset: Tuple[int, int] = (0, 0),
    scale: float = 1.0,
):
    if not QUARTZ_AVAILABLE:
        raise RuntimeError("Quartz not available — macOS only")

    if not path:
        return

    points = [tile_to_screen(r, c, grid_region, window_offset, scale) for r, c in path]

    sx, sy = points[0]
    _post_mouse_event(kCGEventLeftMouseDown, sx, sy)
    time.sleep(PRE_SWIPE_HOLD)

    for x, y in points[1:]:
        _post_mouse_event(kCGEventLeftMouseDragged, x, y)
        time.sleep(TILE_HOLD)

    lx, ly = points[-1]
    _post_mouse_event(kCGEventLeftMouseUp, lx, ly)


def play_words(
    words: List[dict],
    grid_region: Tuple[int, int, int, int],
    window_offset: Tuple[int, int] = (0, 0),
    scale: float = 1.0,
    on_word_played: callable = None,
    pause_event: Optional[threading.Event] = None,
):
    if not QUARTZ_AVAILABLE:
        raise RuntimeError("Quartz not available — macOS only")

    total = len(words)

    logger.info("Clicking grid to focus...")
    focus_window(grid_region, window_offset, scale)

    logger.info(f"Playing {total} words...")

    for i, word_info in enumerate(words):
        if pause_event and pause_event.is_set():
            while pause_event.is_set():
                time.sleep(0.1)

        word = word_info["word"]
        path = word_info["path"]
        pts = word_info["points"]

        logger.info(f"[{i+1}/{total}] Swiping: {word} ({pts} pts, {len(path)} tiles)")

        swipe_word(path, grid_region, window_offset, scale)

        if on_word_played:
            on_word_played(word_info, i, total)

        time.sleep(WORD_DELAY)

    logger.info(f"Done! Played {total} words")
