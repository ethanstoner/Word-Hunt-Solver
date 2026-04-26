"""
OCR module — detect the 4x4 Word Hunt grid and extract letters.
Primary OCR: Tesseract (PSM 8/13/10-inv majority with confidence scores).
Fallback OCR: EasyOCR recognize (bypasses detection for single chars).
Grid detection: HSV tile-color mask → contour fallback → hardcoded estimate.
"""
import logging
from typing import List, Tuple, Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False


# Cached EasyOCR reader
_reader = None


def get_reader():
    """Get or create cached EasyOCR reader."""
    global _reader
    if _reader is None:
        if not EASYOCR_AVAILABLE:
            raise RuntimeError("easyocr not installed: pip install easyocr")
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def detect_grid_region(img: "Image.Image") -> Tuple[int, int, int, int]:
    """
    Detect the 4x4 Word Hunt grid region in the screenshot.
    Returns (x, y, width, height) of the grid area.

    Strategy 1 (primary): HSV color mask for the tan/beige wooden tile color.
    Strategy 2 (fallback): largest square-ish contour in adaptive threshold.
    Strategy 3 (last resort): proportional estimate (device-independent).
    """
    if not CV2_AVAILABLE:
        raise RuntimeError("opencv-python not installed: pip install opencv-python")

    img_array = np.array(img)
    img_h, img_w = img_array.shape[:2]

    # --- Strategy 1: tile color detection in HSV ---
    hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)

    # Word Hunt tiles are tan/beige wooden tiles
    # HSV range: hue ~15-35, saturation ~20-100, value ~150-255
    lower_tile = np.array([10, 20, 140])
    upper_tile = np.array([40, 130, 255])
    mask = cv2.inRange(hsv, lower_tile, upper_tile)

    # Morphological close to merge nearby tile blobs
    kernel = np.ones((20, 20), np.uint8)
    mask_closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best = None
    best_area = 0
    min_area = img_w * img_h * 0.03

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        aspect = w / h if h > 0 else 0
        if 0.7 < aspect < 1.4 and area > min_area:
            if area > best_area:
                best = (x, y, w, h)
                best_area = area

    if best is not None:
        # Pad slightly to include tile edges
        pad = int(img_w * 0.01)
        x, y, w, h = best
        size = max(w, h)
        x = max(0, x - pad)
        y = max(0, y - pad)
        size = min(size + pad * 2, img_w - x, img_h - y)
        logger.info(f"Grid detected via tile color: x={x}, y={y}, w={size}, h={size}")
        return (x, y, size, size)

    # --- Strategy 2: largest square-ish contour in adaptive threshold ---
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
    )
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        aspect = w / h if h > 0 else 0
        if 0.7 < aspect < 1.4 and area > img_w * img_h * 0.05:
            if area > best_area:
                best = (x, y, w, h)
                best_area = area

    if best is not None:
        logger.info(f"Grid detected via contour: x={best[0]}, y={best[1]}, w={best[2]}, h={best[3]}")
        return best

    # --- Strategy 3: proportional estimate (device-independent) ---
    # Word Hunt grid is roughly centered horizontally, in the middle ~60% of the screen
    # These ratios work across different iPhone screen sizes in mirroring
    grid_size = int(img_w * 0.70)
    margin_x = (img_w - grid_size) // 2
    margin_top = int(img_h * 0.40)
    best = (margin_x, margin_top, grid_size, grid_size)
    logger.warning(f"Grid detection fallback (estimated): {best}")
    return best


def extract_cells(img: "Image.Image", grid_region: Tuple[int, int, int, int]) -> List[List["Image.Image"]]:
    """Split the grid region into 4x4 individual cell images."""
    gx, gy, gw, gh = grid_region
    cell_w = gw // 4
    cell_h = gh // 4

    # Add padding inward to avoid tile borders
    pad_x = int(cell_w * 0.15)
    pad_y = int(cell_h * 0.15)

    cells = []
    for row in range(4):
        row_cells = []
        for col in range(4):
            x1 = gx + col * cell_w + pad_x
            y1 = gy + row * cell_h + pad_y
            x2 = gx + (col + 1) * cell_w - pad_x
            y2 = gy + (row + 1) * cell_h - pad_y
            cell = img.crop((x1, y1, x2, y2))
            row_cells.append(cell)
        cells.append(row_cells)

    return cells


_TESS_WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_TESS_CONFIGS = [
    f"--psm 8  --oem 3 -c tessedit_char_whitelist={_TESS_WHITELIST}",
    f"--psm 13 --oem 3 -c tessedit_char_whitelist={_TESS_WHITELIST}",
    # PSM 10 on inverted image catches narrow chars like I that PSM 8/13 misread
    f"--psm 10 --oem 3 -c tessedit_char_whitelist={_TESS_WHITELIST}",
]


def _prep_for_tess(cell_img: "Image.Image"):
    """Return (normal_bw, inverted_bw) arrays ready for Tesseract."""
    arr = np.array(cell_img.resize((256, 256), Image.LANCZOS).convert("L"))
    _, bw = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    padded = cv2.copyMakeBorder(bw, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)
    return padded, cv2.bitwise_not(padded)


def ocr_cell(cell_img: "Image.Image") -> str:
    """
    OCR a single tile cell.

    Primary: Tesseract with three PSM modes (8, 13, 10-inverted).
    Uses Tesseract's per-character confidence scores to pick the best result.
    Fallback: EasyOCR recognize() with forced full-image bounding box.
    """
    # --- Primary: Tesseract ---
    if TESSERACT_AVAILABLE:
        normal, inverted = _prep_for_tess(cell_img)
        best_letter, best_conf = "?", -1

        for cfg, img_v in [
            (_TESS_CONFIGS[0], normal),    # PSM 8 normal
            (_TESS_CONFIGS[1], normal),    # PSM 13 normal
            (_TESS_CONFIGS[2], inverted),  # PSM 10 inverted (catches I, J, etc.)
        ]:
            try:
                data = pytesseract.image_to_data(
                    img_v, config=cfg, output_type=pytesseract.Output.DICT
                )
                for text, conf in zip(data["text"], data["conf"]):
                    text = text.strip().upper()
                    conf = int(conf)
                    if len(text) == 1 and text.isalpha() and conf > best_conf:
                        best_conf = conf
                        best_letter = text
            except Exception:
                pass

        if best_letter != "?":
            return best_letter.lower()

    # --- Fallback: EasyOCR recognize (bypasses detector for narrow chars) ---
    if EASYOCR_AVAILABLE:
        reader = get_reader()
        arr = np.array(cell_img.resize((256, 256), Image.LANCZOS))
        h, w = arr.shape[:2]
        try:
            results = reader.recognize(
                arr,
                horizontal_list=[[0, w, 0, h]],
                free_list=[],
                allowlist=_TESS_WHITELIST,
                detail=1,
            )
            if results:
                best = max(results, key=lambda r: r[2])
                for ch in best[1].strip().upper():
                    if ch.isalpha():
                        return ch.lower()
        except Exception:
            pass

    logger.warning("Could not OCR cell, returning '?'")
    return "?"


def read_board(img: "Image.Image") -> Tuple[List[List[str]], Tuple[int, int, int, int]]:
    """
    Full pipeline: detect grid, extract cells, OCR each letter.
    Returns (4x4 board of letters, grid_region).
    """
    grid_region = detect_grid_region(img)
    cells = extract_cells(img, grid_region)

    board = []
    for row_idx, row in enumerate(cells):
        board_row = []
        for col_idx, cell in enumerate(row):
            letter = ocr_cell(cell)
            board_row.append(letter)
            logger.debug(f"Cell ({row_idx},{col_idx}): '{letter}'")
        board.append(board_row)

    logger.info(f"OCR result: {[''.join(row) for row in board]}")
    return board, grid_region
