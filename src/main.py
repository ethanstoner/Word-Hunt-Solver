"""
Game Pigeon Word Hunt Auto-Solver
Main entry point — orchestrates: capture -> OCR -> solve -> play
Overlay runs on main thread (macOS tkinter requirement), solver on background thread.
Loops automatically — after each game, waits for the next one.
"""
import sys
import time
import logging
import argparse
import threading
from pathlib import Path

from capture import capture_mirroring_window, wait_for_mirroring_window
from ocr import read_board
from solver import solve, solve_board, board_from_string, BOARD_SIZES
from player import play_words
from overlay import SolverOverlay
from config import (
    MAX_WORD_LENGTH, MAX_WORDS_TO_PLAY, SHOW_OVERLAY,
    DEBUG, SAVE_SCREENSHOTS, WORD_DELAY,
)

try:
    from pynput import keyboard as kb
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("wordhunt")


def is_active_game(image):
    """Check if the screen shows an active Word Hunt game."""
    import numpy as np, cv2
    arr = np.array(image)
    h, w = arr.shape[:2]

    header = arr[int(h*0.05):int(h*0.13), int(w*0.1):int(w*0.9)]
    gray_header = cv2.cvtColor(header, cv2.COLOR_RGB2GRAY)
    white_pixels = float(np.sum(gray_header > 200))
    white_ratio = white_pixels / gray_header.size if gray_header.size > 0 else 0

    if white_ratio < 0.03:
        return None

    hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
    lower_tile = np.array([10, 20, 140])
    upper_tile = np.array([40, 130, 255])
    mask = cv2.inRange(hsv, lower_tile, upper_tile)
    kernel = np.ones((20, 20), np.uint8)
    mask_closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(mask_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best = None
    best_area = 0
    MIN_GRID_SIZE = 450
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        area = bw * bh
        aspect = bw / bh if bh > 0 else 0
        if 0.8 < aspect < 1.2 and bw >= MIN_GRID_SIZE:
            if area > best_area:
                pad = int(w * 0.01)
                size = max(bw, bh)
                best = (max(0, x - pad), max(0, y - pad),
                        min(size + pad*2, w - x, h - y),
                        min(size + pad*2, w - x, h - y))
                best_area = area

    return best


def play_one_game(args, overlay, pause_event, window_info, retina_scale, img, grid_region):
    """Run one full game: OCR -> confirm -> solve -> play."""
    layout = args.board

    if overlay:
        overlay.set_status("Reading board (OCR)...")

    board, grid_region = read_board(img)

    if layout == "4x4" and isinstance(board[0], list):
        flat_letters = [c for row in board for c in row]
    else:
        flat_letters = list(board)

    if overlay and layout == "4x4":
        overlay.set_board(board)

    print(f"\nDetected board ({layout}):")
    if layout == "4x4" and isinstance(board[0], list):
        for row in board:
            print("  " + " ".join(c.upper() for c in row))

    has_errors = "?" in flat_letters
    if has_errors:
        logger.warning("Some letters could not be recognized!")

    if overlay:
        overlay.set_status("Edit tiles, then ENTER")
        overlay.enter_edit_mode()
        print("\nCheck the overlay — click any tile to edit, then press ENTER.")
        board = overlay.wait_for_confirmation(timeout=120)
        flat_letters = [c for row in board for c in row]
        print(f"Confirmed board:")
        for row in board:
            print("  " + " ".join(c.upper() for c in row))
    else:
        if has_errors:
            print(f"\n[!] ERRORS — Type 16 correct letters or ENTER to accept:")
            try:
                correction = input("> ").strip()
            except EOFError:
                correction = ""
            if correction:
                letters = correction.lower().replace(" ", "")
                if len(letters) == 16 and letters.isalpha():
                    board = [list(letters[i:i+4]) for i in range(0, 16, 4)]
                    flat_letters = list(letters)

    if overlay:
        overlay.set_board(board)
        overlay.set_status("Solving...")

    start_time = time.time()
    words = solve(flat_letters, layout=layout, max_length=args.max_length, max_words=args.max_words)
    solve_time = time.time() - start_time

    total_points = sum(w["points"] for w in words)
    logger.info(f"Found {len(words)} words in {solve_time:.2f}s (potential: {total_points} pts)")

    if overlay:
        overlay.set_words(words)
        overlay.set_status(f"Found {len(words)} words ({total_points} pts)")

    print(f"\nFound {len(words)} words in {solve_time:.2f}s:")
    for i, w in enumerate(words[:15]):
        print(f"  {i+1:>2}. {w['word']:<12} {w['points']:>4} pts")
    if len(words) > 15:
        print(f"  ... and {len(words) - 15} more")

    if not args.no_play and grid_region and window_info:
        print(f"\nPlaying {len(words)} words...")
        time.sleep(0.5)

        if overlay:
            overlay.set_status("Playing...")

        def on_word_played(word_info, idx, total):
            if overlay:
                overlay.set_current_word(word_info["word"])
                overlay.highlight_path(word_info["path"])
                overlay.set_progress(idx + 1, total)
                overlay.mark_word_played(idx)

        play_words(
            words,
            grid_region=grid_region,
            window_offset=(window_info["x"], window_info["y"]),
            scale=retina_scale,
            on_word_played=on_word_played,
            pause_event=pause_event,
        )

        if overlay:
            overlay.set_status(f"Done! {len(words)} words, {total_points} pts")
            overlay.set_current_word("")
            overlay.highlight_path([])

        print(f"\nDone! Played {len(words)} words (potential: {total_points} pts)")
    elif args.no_play:
        print("\n(--no-play mode, not auto-playing)")


def run_solver(args, overlay, pause_event, stop_event):
    """Main solver loop — runs games continuously."""

    game_count = 0

    while not stop_event.is_set():
        try:
            if overlay:
                overlay.reset()
                overlay.set_status("Waiting for game...")

            if args.manual and game_count == 0:
                board = board_from_string(args.manual, layout=args.board)
                logger.info(f"Manual board: {[''.join(r) for r in board]}")
                # Manual mode only runs once
                flat_letters = [c for row in board for c in row]
                words = solve(flat_letters, layout=args.board, max_length=args.max_length, max_words=args.max_words)
                total_points = sum(w["points"] for w in words)
                print(f"\nFound {len(words)} words ({total_points} pts)")
                for i, w in enumerate(words[:15]):
                    print(f"  {i+1:>2}. {w['word']:<12} {w['points']:>4} pts")
                if len(words) > 15:
                    print(f"  ... and {len(words) - 15} more")
                print("\n(Manual mode -- can't auto-play without screen capture)")
                break

            window_info = wait_for_mirroring_window(timeout=30)

            print(f"\n{'='*40}")
            print(f"  Waiting for game... press Start in Word Hunt")
            print(f"  (Ctrl+C to quit)")
            print(f"{'='*40}")

            # Poll for active game
            while not stop_event.is_set():
                img, _ = capture_mirroring_window()
                retina_scale = img.size[0] / window_info["width"] if window_info["width"] else 1.0
                detected = is_active_game(img)

                if detected:
                    time.sleep(0.3)
                    img, _ = capture_mirroring_window()
                    detected = is_active_game(img)
                    if detected:
                        logger.info(f"Active game detected! Grid: {detected}")
                        break

                time.sleep(0.5)

            if stop_event.is_set():
                break

            game_count += 1
            print(f"\n--- Game #{game_count} ---")

            if SAVE_SCREENSHOTS:
                debug_dir = Path(__file__).parent.parent / "debug"
                debug_dir.mkdir(exist_ok=True)
                img.save(debug_dir / "capture.png")

            play_one_game(args, overlay, pause_event, window_info, retina_scale, img, detected)

            if overlay:
                overlay.set_status(f"Game #{game_count} done — waiting for next game...")

            # Wait for the game screen to go away before scanning for the next one
            print("\nWaiting for next game...")
            time.sleep(3)

        except KeyboardInterrupt:
            print("\nAborted by user.")
            break
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            if overlay:
                overlay.set_status(f"Error: {e}")
            time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description="Word Hunt Auto-Solver")
    parser.add_argument("--max-words", type=int, default=MAX_WORDS_TO_PLAY,
                       help="Max words to play")
    parser.add_argument("--max-length", type=int, default=MAX_WORD_LENGTH,
                       help="Max word length to search")
    parser.add_argument("--no-overlay", action="store_true",
                       help="Disable the overlay window")
    parser.add_argument("--no-play", action="store_true",
                       help="Find words but don't auto-play them")
    parser.add_argument("--debug", action="store_true",
                       help="Enable debug logging")
    parser.add_argument("--delay", type=float, default=WORD_DELAY,
                       help="Delay between words (seconds)")
    parser.add_argument("--manual", type=str, default=None,
                       help="Manual board input (e.g. 'ABCDEFGHIJKLMNOP')")
    parser.add_argument("--board", type=str, default="4x4",
                       choices=["4x4", "5x5", "donut", "cross"],
                       help="Board layout (default: 4x4)")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    pause_event = threading.Event()
    stop_event = threading.Event()

    overlay = None
    if SHOW_OVERLAY and not args.no_overlay:
        overlay = SolverOverlay()

    if PYNPUT_AVAILABLE:
        def on_press(key):
            if key == kb.Key.esc:
                if stop_event.is_set():
                    return False
                if pause_event.is_set():
                    pause_event.clear()
                    print("\n▶ Resumed (ESC to pause)")
                    if overlay:
                        overlay.set_status("Playing...")
                else:
                    pause_event.set()
                    print("\n⏸ Paused (ESC to resume)")
                    if overlay:
                        overlay.set_status("⏸ PAUSED -- press ESC to resume")
        key_listener = kb.Listener(on_press=on_press)
        key_listener.daemon = True
        key_listener.start()
    else:
        logger.warning("pynput not installed -- ESC pause unavailable")

    solver_thread = threading.Thread(
        target=run_solver, args=(args, overlay, pause_event, stop_event), daemon=True
    )
    solver_thread.start()

    try:
        if overlay:
            overlay.start()
        else:
            solver_thread.join()
    except KeyboardInterrupt:
        print("\nAborted by user.")
    finally:
        stop_event.set()
        if overlay:
            overlay.stop()


if __name__ == "__main__":
    main()
