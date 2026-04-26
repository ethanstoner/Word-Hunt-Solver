# Word Hunt Solver

Automated solver for Game Pigeon's **Word Hunt** on macOS. Uses **iPhone Mirroring** to capture the game board from your iPhone, OCRs the 4x4 letter grid, finds all valid words using DFS with prefix pruning, then auto-swipes them on the mirrored phone screen — all in real time.

> **macOS only.** This tool requires a Mac running macOS 15+ (Sequoia) with iPhone Mirroring and a connected iPhone. It does not work on Windows or Linux.

## How It Works

Word Hunt is played on your iPhone through iMessage. This solver uses macOS's **iPhone Mirroring** feature (introduced in macOS Sequoia) to mirror your iPhone screen to your Mac. Once mirrored, the solver:

1. **Watches** for an active Word Hunt game to appear on the mirrored screen
2. **Captures** the mirrored window via macOS Quartz screen capture APIs
3. **Detects** the 4x4 tile grid using computer vision (HSV color masking on the wooden tiles)
4. **OCRs** each tile letter using Tesseract (with EasyOCR as fallback)
5. **Shows** the detected board in an overlay window — you can click any tile to fix OCR mistakes
6. **Solves** the board using DFS with dictionary prefix pruning (~200 words in <0.2 seconds)
7. **Auto-swipes** each word on the mirrored screen using low-level macOS mouse events
8. **Loops** — automatically waits for the next game when the current one finishes

The solver uses Quartz `CGEventCreateMouseEvent` with `kCGEventLeftMouseDragged` to simulate swipe gestures. This is required because iPhone Mirroring ignores standard mouse movement events (`kCGEventMouseMoved`) during drags — a limitation discovered through testing 5 different input methods.

## Features

- **Automatic game detection** — watches for the Word Hunt grid to appear, starts solving instantly
- **Real-time overlay** — shows detected board, word list with points, current word, and progress
- **Editable board** — click any tile in the overlay to fix OCR mistakes before solving
- **Fast swiping** — ~3 words per second, ~250 words per 80-second game
- **Pause/resume** — press ESC to pause swiping, ESC again to resume
- **Continuous mode** — automatically waits for the next game after each round
- **Device-independent** — works with any iPhone model (no hardcoded screen dimensions)

## Requirements

- **macOS 15+ (Sequoia)** with iPhone Mirroring
- **iPhone** connected to the same Apple ID with iPhone Mirroring enabled
- **Python 3.10+**
- **Tesseract OCR** (`brew install tesseract`)

### macOS Permissions

You must grant these in **System Settings > Privacy & Security**:
- **Screen Recording** — allow Terminal (or your terminal app)
- **Accessibility** — allow Terminal (or your terminal app)

Without these, the solver cannot capture the mirrored screen or simulate mouse input.

## Installation

```bash
# Clone the repo
git clone https://github.com/ethanstoner/Word-Hunt-Solver.git
cd Word-Hunt-Solver

# Install Tesseract (if not already installed)
brew install tesseract

# Set up Python virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

### Quick Launch (Double-Click)

Double-click **`Word Hunt Solver.command`** in Finder. It sets up the environment automatically and launches the solver.

### Command Line

```bash
source venv/bin/activate
cd src
python main.py
```

### Step-by-Step

1. Open **iPhone Mirroring** on your Mac (your iPhone screen appears on your Mac)
2. Launch the solver (`python main.py` or double-click the `.command` file)
3. The overlay window appears, showing "Waiting for game..."
4. On your iPhone (via the mirrored screen), open a **Word Hunt** game in iMessage and press **Start**
5. The solver detects the grid, OCRs the letters, and shows them in the overlay
6. **Review the board** — click any tile to fix mistakes, then press **Enter** to confirm
7. The solver finds all valid words and starts swiping them automatically
8. When the game ends, it waits for the next one — no restart needed

### Options

```
python main.py                              # Full auto mode with overlay
python main.py --no-overlay                 # Run without the GUI overlay
python main.py --no-play                    # Find words but don't auto-swipe
python main.py --manual ABCDEFGHIJKLMNOP    # Test solver with manual letters
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

### Why Quartz CGEvents?

PyAutoGUI's `moveTo()` sends `kCGEventMouseMoved` events, which iPhone Mirroring ignores when the mouse button is held down. For swipe gestures to register, you must send `kCGEventLeftMouseDragged` events via `CGEventCreateMouseEvent` directly. This was discovered through systematic A/B testing of 5 different input methods — only the raw CGEvent approach works.

### Grid Detection

The solver uses HSV color masking to detect the tan/beige wooden tiles, then finds the largest square-ish contour. It also verifies the WORDS/SCORE header text is present (white text on dark background) to distinguish real games from chat preview thumbnails. All detection is proportional — no hardcoded pixel values — so it works with any iPhone model and screen resolution.

### Swipe Timing

Tested at 6 speed profiles from conservative (0.63s/word) to ludicrous (0.09s/word). The optimal profile is **0.32s per word** (`pre_hold=0.04s`, `tile_hold=0.025s`, `word_delay=0.18s`) — 100% reliable at ~3 words/second.

### Solver Algorithm

- DFS from every starting tile on the 4x4 grid
- O(1) visited array for path tracking
- Prefix set pruning — if the current string isn't a prefix of any dictionary word, prune immediately
- Results sorted by points descending, then word length descending (highest-value words first)
- Supports 4x4, 5x5, Donut, and Cross board layouts

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "iPhone Mirroring window not found" | Make sure iPhone Mirroring is open and your iPhone is connected |
| Solver doesn't detect the game | Make sure the full game grid is visible (not the "How to play" screen) |
| OCR reads wrong letters | Click the wrong tiles in the overlay to fix them before pressing Enter |
| Swipes don't register | Check Accessibility permission is granted in System Settings |
| Permission denied errors | Grant Screen Recording + Accessibility to your terminal app |
| `tesseract` not found | Run `brew install tesseract` |

## Credits

- Solver algorithm inspired by [k-gerner/Game-Pigeon-Solvers](https://github.com/k-gerner/Game-Pigeon-Solvers)
- Dictionary from standard Scrabble word lists

## License

MIT
