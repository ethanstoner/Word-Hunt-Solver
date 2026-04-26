# Word Hunt Solver

Automated solver for Game Pigeon's **Word Hunt** on macOS. Captures the iPhone Mirroring window, OCRs the 4x4 letter grid, finds all valid words using DFS with prefix pruning, then auto-swipes them on the mirrored phone screen.

https://github.com/user-attachments/assets/demo.gif

## Features

- **Automatic game detection** — watches for the Word Hunt grid to appear, starts solving instantly
- **Real-time overlay** — shows detected board, word list, current word, and progress
- **Editable board** — click any tile in the overlay to fix OCR mistakes before solving
- **Fast swiping** — uses low-level macOS Quartz CGEvents for reliable, fast input (~3 words/second)
- **Pause/resume** — press ESC to pause swiping, ESC again to resume
- **Continuous mode** — automatically waits for the next game after each round
- **Device-independent** — works with any iPhone model via screen mirroring (no hardcoded dimensions)

## How It Works

1. **Capture** — finds the iPhone Mirroring window via Quartz `CGWindowListCopyWindowInfo` and screenshots it
2. **Detect** — uses HSV color masking to locate the wooden tile grid, verifies the WORDS/SCORE header is present
3. **OCR** — extracts each cell and reads letters via Tesseract (primary) with EasyOCR fallback
4. **Confirm** — shows the detected board in the overlay; click any tile to edit, press Enter to confirm
5. **Solve** — DFS traversal with dictionary prefix pruning finds all valid 3-10 letter words
6. **Play** — swipes each word using `CGEventCreateMouseEvent` with `kCGEventLeftMouseDragged` events
7. **Loop** — waits for the next game automatically

## Requirements

- **macOS** (uses Quartz framework for screen capture and mouse events)
- **Python 3.10+**
- **iPhone Mirroring** app open with an active Word Hunt game
- **Tesseract OCR** installed (`brew install tesseract`)

### macOS Permissions

Grant these in **System Settings > Privacy & Security**:
- **Screen Recording** — allow Terminal (or your terminal app)
- **Accessibility** — allow Terminal (or your terminal app)

## Installation

```bash
git clone https://github.com/ethanstoner/gamepigeon-solver.git
cd gamepigeon-solver
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
brew install tesseract  # if not already installed
```

## Usage

### Quick Launch (Double-Click)

Double-click **`Word Hunt Solver.command`** in Finder. It sets up the environment and launches the solver automatically.

### Command Line

```bash
source venv/bin/activate
cd src
python main.py
```

The solver will:
1. Open the overlay window
2. Wait for an active Word Hunt game in iPhone Mirroring
3. Press Start in the game — the solver detects the grid automatically
4. Review the detected board in the overlay, click tiles to fix any errors
5. Press Enter to confirm — it solves and starts swiping

### Options

```
python main.py                              # Full auto mode with overlay
python main.py --no-overlay                 # Run without the GUI overlay
python main.py --no-play                    # Find words but don't auto-swipe
python main.py --manual ABCDEFGHIJKLMNOP    # Test with manual letters
python main.py --max-words 100              # Limit words to play (default: 500)
python main.py --debug                      # Enable debug logging
```

### Controls

| Key | Action |
|-----|--------|
| **Enter** | Confirm board and start playing (during edit mode) |
| **ESC** | Pause/resume swiping |
| **Ctrl+C** | Quit |
| **Click tile** | Select tile to edit (during edit mode) |
| **Type letter** | Replace selected tile, auto-advances to next |

## Project Structure

```
src/
  main.py       — entry point, game loop, overlay/solver coordination
  capture.py    — finds iPhone Mirroring window, takes screenshots (Quartz)
  ocr.py        — detects 4x4 grid + OCRs letters (OpenCV + Tesseract/EasyOCR)
  solver.py     — DFS word finder with dictionary prefix pruning
  player.py     — simulates swipe gestures via Quartz CGEvents
  overlay.py    — tkinter always-on-top status window with editable board
  config.py     — tunable settings
data/
  letters10.txt — dictionary (~197k words, up to 10 letters)
```

## Technical Details

### Why Quartz CGEvents Instead of PyAutoGUI?

PyAutoGUI's `moveTo()` sends `kCGEventMouseMoved` events, which iPhone Mirroring ignores when the mouse button is held down. For swipe gestures to register, you must send `kCGEventLeftMouseDragged` events via `CGEventCreateMouseEvent` directly. This was discovered through systematic testing of 5 different input methods.

### Grid Detection

The solver uses HSV color masking to detect the tan/beige wooden tiles, then finds the largest square-ish contour. This is device-independent — it works regardless of screen size or resolution. The system also verifies the WORDS/SCORE header is present to avoid false positives from chat preview thumbnails.

### Swipe Timing

Tested at various speeds. The "Faster" profile (`pre_hold=0.04s`, `tile_hold=0.025s`, `word_delay=0.18s`) gives ~0.32s per word with 100% reliability, allowing ~250 words per 80-second game.

## Solver Algorithm

- DFS from every starting tile
- O(1) visited array for path tracking
- Prefix set pruning — if the current string isn't a prefix of any dictionary word, prune immediately
- Results sorted by points descending, then word length descending
- Supports 4x4, 5x5, Donut, and Cross board layouts

## Credits

- Solver algorithm inspired by [k-gerner/Game-Pigeon-Solvers](https://github.com/k-gerner/Game-Pigeon-Solvers)
- Dictionary from standard Scrabble word lists

## License

MIT
