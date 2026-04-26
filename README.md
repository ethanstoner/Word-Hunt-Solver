# Word Hunt Solver

A real-time computer vision pipeline that captures a live iPhone screen through macOS mirroring, recognizes game boards via OCR, finds optimal words using graph search algorithms, and executes them through low-level input simulation — all fully automated, no jailbreak or game modification required.

Built with **Python**, **OpenCV**, **Tesseract OCR**, and **macOS Quartz CoreGraphics APIs**.

## Demo

```
Detected board:
  S  T  A  R
  E  N  I  L
  D  O  C  K
  B  U  M  P

Found 247 words in 0.18s — playing at ~3 words/sec...

  1. docent       1400 pts
  2. instar       1400 pts
  3. instal       1400 pts
  4. nicest       1400 pts
  ...
  247 words played · Estimated score: 42,600 pts
```

## The Problem

Word Hunt gives you 80 seconds to find words on a 4x4 letter grid by swiping through adjacent tiles. A human player finds 20-30 words per round. This solver finds **200+ words** and executes them faster than any human could — completing ~250 words in a single game.

## Pipeline

```
iPhone Screen ──► macOS Mirroring Window ──► Quartz Screen Capture
       ──► OpenCV Grid Detection ──► Tesseract OCR
       ──► DFS Solver (197k word dictionary, prefix pruning)
       ──► CGEvent Touch Simulation ──► Words played on phone
```

**1. Screen Capture** — Locates the iPhone Mirroring window using Quartz `CGWindowListCopyWindowInfo` and captures frames via `CGWindowListCreateImage`. Continuously monitors for new games by polling for the Word Hunt grid.

**2. Board Recognition** — Isolates game tiles using OpenCV HSV color masking on the wooden tile color range, finds the grid contour, segments into 16 cells, and runs Tesseract OCR on each (EasyOCR fallback). All detection is proportional — zero hardcoded pixel values — so it works across every iPhone model and resolution.

**3. Word Finding** — DFS from all 16 starting positions, exploring 8-directional adjacency with O(1) visited tracking. A prefix set built from a 197k-word dictionary provides O(1) pruning at every node — if the current path isn't a prefix of any valid word, the entire subtree is abandoned. Solves any board in under 200ms.

**4. Input Simulation** — Translates word paths to screen coordinates and simulates swipe gestures using Quartz `CGEventCreateMouseEvent` with `kCGEventLeftMouseDragged`. Standard input APIs don't work here — this required reverse-engineering the exact event type iPhone Mirroring's compositor accepts.

**5. Game Loop** — Detects game start/end automatically and restarts the pipeline with zero manual intervention.

## Technical Highlights

### Reverse-Engineering iPhone Mirroring Input

iPhone Mirroring silently drops `kCGEventMouseMoved` events during mouse-down state, which means every standard macOS automation tool (PyAutoGUI, AppleScript, cliclick) fails to produce swipe gestures. Through systematic A/B testing of 5 different input methods, I discovered that only raw `kCGEventLeftMouseDragged` events via the Quartz CoreGraphics C API are accepted by the mirroring compositor. This is undocumented behavior.

### Solver Performance

The DFS solver with prefix-set pruning reduces the search space from ~12 million potential paths to a few thousand, finding every valid word on any board in **<200ms**. Words are scored and sorted to maximize points — longest, highest-value words are played first.

### Adaptive Computer Vision

The grid detection pipeline uses no hardcoded coordinates or screen dimensions:
- HSV color masking isolates wooden tiles from any background
- Contour analysis identifies the largest square region as the game board
- Header text verification (OCR for "WORDS"/"SCORE") distinguishes active games from chat preview thumbnails
- Proportional cell segmentation adapts to any detected grid size

### Swipe Speed Optimization

Benchmarked 6 speed profiles from conservative (0.63s/word) to aggressive (0.09s/word). Optimal configuration: **0.32s/word** with `pre_hold=0.04s`, `tile_hold=0.025s`, `word_delay=0.18s` — 100% input reliability at ~3 words/second.

## Skills & Technologies

| Area | Implementation |
|------|---------------|
| **Computer Vision** | OpenCV HSV masking, contour detection, adaptive thresholding, image segmentation |
| **Optical Character Recognition** | Tesseract + EasyOCR dual-engine pipeline with preprocessing for single-character accuracy |
| **Graph Algorithms** | DFS with prefix-set pruning on 8-directional adjacency graph, O(1) visited tracking |
| **macOS Systems Programming** | Quartz CoreGraphics API — `CGWindowListCreateImage`, `CGEventCreateMouseEvent`, window enumeration |
| **Reverse Engineering** | Discovered undocumented iPhone Mirroring input constraints through systematic input method testing |
| **Real-Time Processing** | Sub-200ms solve times, continuous game detection, timing-critical input simulation |
| **Software Architecture** | 7 focused modules (~1,500 LOC), clean pipeline design, separation of concerns |

## Project Structure

```
src/
  main.py       — Pipeline orchestration + game loop               (331 lines)
  capture.py    — Quartz window detection + screenshot capture      (130 lines)
  ocr.py        — OpenCV grid detection + Tesseract/EasyOCR         (257 lines)
  solver.py     — DFS word finder with prefix pruning               (192 lines)
  player.py     — CGEvent-based swipe simulation                    (137 lines)
  overlay.py    — Tkinter real-time status overlay                  (418 lines)
  config.py     — Centralized configuration                         (20 lines)
data/
  letters10.txt — Dictionary: 197,762 words, up to 10 letters
```

## Features

- **Fully automated** — detects game start, solves, plays, waits for next game
- **Real-time overlay** — shows detected board, word list, current word, and progress
- **Editable board** — click tiles in the overlay to fix OCR mistakes before solving
- **Pause/resume** — press ESC to pause swiping mid-game
- **Device-independent** — works with any iPhone model, no configuration needed
- **~250 words per game** at ~3 words/second

## Setup

Requires **macOS 15+** (Sequoia) with iPhone Mirroring and a connected iPhone.

```bash
git clone https://github.com/ethanstoner/Word-Hunt-Solver.git
cd Word-Hunt-Solver

brew install tesseract
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Grant **Screen Recording** and **Accessibility** permissions to your terminal app in System Settings > Privacy & Security.

## Usage

```bash
# Quick launch (double-click in Finder)
open "Word Hunt Solver.command"

# Or from terminal
source venv/bin/activate && cd src && python main.py
```

| Option | Description |
|--------|-------------|
| `--manual LETTERS` | Test solver with 16 manual letters |
| `--no-play` | Find words without auto-swiping |
| `--no-overlay` | Disable the GUI overlay |
| `--max-words N` | Limit words played (default: 500) |
| `--debug` | Enable verbose logging |

| Control | Action |
|---------|--------|
| **Enter** | Confirm board and start playing |
| **ESC** | Pause / resume swiping |
| **Ctrl+C** | Quit |
| **Click tile** | Edit a misread letter |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "iPhone Mirroring window not found" | Open iPhone Mirroring and connect your iPhone |
| Solver doesn't detect the game | Ensure the full grid is visible (not the "How to play" screen) |
| OCR reads wrong letters | Click wrong tiles in overlay to correct before pressing Enter |
| Swipes don't register | Grant Accessibility permission in System Settings |
| `tesseract` not found | Run `brew install tesseract` |

## Credits

Solver algorithm inspired by [k-gerner/Game-Pigeon-Solvers](https://github.com/k-gerner/Game-Pigeon-Solvers). Dictionary sourced from standard Scrabble word lists.

## License

MIT
