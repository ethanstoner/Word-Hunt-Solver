"""
macOS screen capture — find iPhone Mirroring window and grab screenshots.
Uses Quartz (CoreGraphics) for window discovery and screenshot capture.
"""
import subprocess
import time
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import Quartz
    from Quartz import (
        CGWindowListCopyWindowInfo,
        kCGWindowListOptionOnScreenOnly,
        kCGNullWindowID,
        CGWindowListCreateImage,
        CGRectMake,
        kCGWindowListOptionIncludingWindow,
        kCGWindowImageBoundsIgnoreFraming,
    )
    from AppKit import NSBitmapImageRep, NSPNGFileType
    import objc
    QUARTZ_AVAILABLE = True
except ImportError:
    QUARTZ_AVAILABLE = False

try:
    from PIL import Image
    import io
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


MIRROR_WINDOW_NAMES = ["iPhone Mirroring", "iPhone-Mirroring"]
MIRROR_OWNER_NAMES = ["iPhone Mirroring"]


def find_mirroring_window() -> Optional[dict]:
    """Find the iPhone Mirroring window and return its info."""
    if not QUARTZ_AVAILABLE:
        raise RuntimeError(
            "Quartz framework not available. This must run on macOS with pyobjc installed.\n"
            "Install with: pip install pyobjc-framework-Quartz pyobjc-framework-Cocoa"
        )

    window_list = CGWindowListCopyWindowInfo(
        kCGWindowListOptionOnScreenOnly, kCGNullWindowID
    )

    for window in window_list:
        owner = window.get("kCGWindowOwnerName", "")
        name = window.get("kCGWindowName", "")

        if owner in MIRROR_OWNER_NAMES or name in MIRROR_WINDOW_NAMES:
            bounds = window.get("kCGWindowBounds", {})
            return {
                "id": window.get("kCGWindowNumber"),
                "owner": owner,
                "name": name,
                "x": int(bounds.get("X", 0)),
                "y": int(bounds.get("Y", 0)),
                "width": int(bounds.get("Width", 0)),
                "height": int(bounds.get("Height", 0)),
            }

    return None


def capture_window(window_info: dict) -> "Image.Image":
    """Capture a screenshot of the specified window, return as PIL Image."""
    if not QUARTZ_AVAILABLE:
        raise RuntimeError("Quartz not available — macOS only")
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow not installed: pip install Pillow")

    window_id = window_info["id"]
    bounds = CGRectMake(
        window_info["x"], window_info["y"],
        window_info["width"], window_info["height"],
    )

    image_ref = CGWindowListCreateImage(
        bounds,
        kCGWindowListOptionIncludingWindow,
        window_id,
        kCGWindowImageBoundsIgnoreFraming,
    )

    if image_ref is None:
        raise RuntimeError("Failed to capture window screenshot")

    # Convert CGImage to PIL Image
    bitmapRep = NSBitmapImageRep.alloc().initWithCGImage_(image_ref)
    png_data = bitmapRep.representationUsingType_properties_(NSPNGFileType, None)
    img = Image.open(io.BytesIO(png_data))

    return img


def capture_mirroring_window() -> Tuple["Image.Image", dict]:
    """Find and capture the iPhone Mirroring window. Returns (image, window_info)."""
    window = find_mirroring_window()
    if window is None:
        raise RuntimeError(
            "iPhone Mirroring window not found. Make sure:\n"
            "1. iPhone Mirroring app is open\n"
            "2. Your iPhone is connected and mirroring is active\n"
            "3. The mirroring window is visible (not minimized)"
        )

    logger.debug(f"Found mirroring window: {window['width']}x{window['height']} at ({window['x']}, {window['y']})")
    img = capture_window(window)
    return img, window


def wait_for_mirroring_window(timeout: int = 30, poll_interval: float = 1.0) -> dict:
    """Wait for the iPhone Mirroring window to appear."""
    logger.info("Waiting for iPhone Mirroring window...")
    start = time.time()
    while time.time() - start < timeout:
        window = find_mirroring_window()
        if window:
            logger.info(f"Found mirroring window after {time.time() - start:.1f}s")
            return window
        time.sleep(poll_interval)

    raise TimeoutError(f"iPhone Mirroring window not found after {timeout}s")
