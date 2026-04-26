"""
Overlay — always-on-top window showing solver state.

Displays:
- 4x4 grid with clickable tiles for editing
- Word list with execution order and completion status
- Live status / progress
"""
import tkinter as tk
from tkinter import font as tkfont
import threading
from typing import List, Optional, Tuple


# ── colours ──────────────────────────────────────────────────────────────────
BG        = "#0d0d14"
CARD      = "#13131f"
TILE_DEF  = "#1a1a2e"
TILE_PATH = "#e94560"
TILE_DONE = "#2a2a4e"
TILE_NEXT = "#f5a623"
TILE_SEL  = "#3a3a6e"
TILE_ERR  = "#8b0000"
FG        = "#e0e0e0"
FG_DIM    = "#555566"
ACCENT    = "#e94560"
GREEN     = "#2ecc71"
ORANGE    = "#f5a623"


class SolverOverlay:
    """Always-on-top overlay window for the Word Hunt solver."""

    def __init__(self):
        self.root = None
        self.thread = None
        self._running = False
        self._lock = threading.Lock()

        # State
        self._status     = "Watching for game..."
        self._board: Optional[List[List[str]]] = None
        self._words: List[dict] = []
        self._current_idx: int = -1
        self._current_path: List[Tuple[int,int]] = []
        self._played_indices: set = set()

        # Edit mode
        self._edit_mode = False
        self._selected_tile: Optional[Tuple[int,int]] = None
        self._board_confirmed = threading.Event()

        # Widget refs
        self._status_lbl  = None
        self._board_lbls: List[List[tk.Label]] = []
        self._word_frame  = None
        self._word_rows: List[dict] = []
        self._prog_lbl    = None
        self._go_btn      = None
        self._go_frame    = None

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        """Start the overlay on the main thread (blocks)."""
        self._running = True
        self._run()

    def stop(self):
        self._running = False
        if self.root:
            self.root.after(0, self.root.destroy)

    def reset(self):
        with self._lock:
            self._board = None
            self._words = []
            self._current_idx = -1
            self._current_path = []
            self._played_indices = set()
            self._edit_mode = False
            self._selected_tile = None
        self._board_confirmed.clear()

    # ── public API (called from solver thread) ────────────────────────────────

    def set_status(self, text: str):
        with self._lock:
            self._status = text

    def set_board(self, board: List[List[str]]):
        with self._lock:
            self._board = [list(row) for row in board]

    def enter_edit_mode(self):
        """Enable tile editing. Called from solver thread."""
        with self._lock:
            self._edit_mode = True
            self._selected_tile = None
        self._board_confirmed.clear()
        if self.root:
            self.root.after(100, self._show_edit_ui)

    def wait_for_confirmation(self, timeout=None) -> List[List[str]]:
        """Block until user clicks GO. Returns the (possibly edited) board."""
        self._board_confirmed.wait(timeout=timeout)
        with self._lock:
            self._edit_mode = False
            self._selected_tile = None
            return [list(row) for row in self._board]

    def set_words(self, words: List[dict]):
        with self._lock:
            self._words = list(words)
            self._played_indices = set()
            self._current_idx = -1
        if self.root:
            self.root.after(0, self._rebuild_word_list)

    def set_current_word(self, word: str):
        with self._lock:
            for i, w in enumerate(self._words):
                if w["word"] == word:
                    self._current_idx = i
                    self._current_path = []
                    break
        if self.root:
            self.root.after(0, self._refresh_word_list)

    def mark_word_played(self, idx: int):
        with self._lock:
            self._played_indices.add(idx)
        if self.root:
            self.root.after(0, self._refresh_word_list)

    def highlight_path(self, path: List[Tuple[int,int]]):
        with self._lock:
            self._current_path = list(path) if path else []
        if self.root:
            self.root.after(0, self._refresh_board)

    def set_progress(self, done: int, total: int):
        def _upd():
            if self._prog_lbl:
                self._prog_lbl.config(text=f"{done} / {total} words  ({done*100//total if total else 0}%)")
        if self.root:
            self.root.after(0, _upd)

    # ── internal ──────────────────────────────────────────────────────────────

    def _run(self):
        import os, signal
        self.root = tk.Tk()
        self.root.title("Word Hunt Solver")
        self.root.attributes("-topmost", True)
        self.root.configure(bg=BG)
        self.root.geometry("300x680+700+60")
        self.root.resizable(False, True)
        try:
            self.root.attributes("-alpha", 0.95)
        except tk.TclError:
            pass

        self.root.protocol("WM_DELETE_WINDOW", lambda: os.kill(os.getpid(), signal.SIGTERM))
        self.root.bind("<Key>", self._on_key)

        self._build_ui()
        self._update_loop()
        self.root.mainloop()

    def _build_ui(self):
        root = self.root

        # ── header ──
        hdr = tk.Frame(root, bg=BG)
        hdr.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(hdr, text="⬡ WORD HUNT", font=("Menlo", 13, "bold"),
                 bg=BG, fg=ACCENT).pack(side="left")

        self._status_lbl = tk.Label(hdr, text="", font=("Menlo", 9),
                                    bg=BG, fg=FG_DIM, anchor="e")
        self._status_lbl.pack(side="right")

        # ── board ──
        board_outer = tk.Frame(root, bg=CARD, padx=10, pady=10)
        board_outer.pack(padx=12, pady=(0, 6))

        self._board_lbls = []
        for r in range(4):
            row = []
            for c in range(4):
                lbl = tk.Label(board_outer, text="·",
                               font=("Menlo", 17, "bold"),
                               width=3, height=1,
                               bg=TILE_DEF, fg=FG,
                               relief="flat", borderwidth=0,
                               cursor="hand2")
                lbl.grid(row=r, column=c, padx=3, pady=3)
                lbl.bind("<Button-1>", lambda e, row=r, col=c: self._on_tile_click(row, col))
                row.append(lbl)
            self._board_lbls.append(row)

        # ── edit hint (hidden until edit mode) ──
        self._go_frame = tk.Frame(root, bg=BG)
        self._hint_lbl = tk.Label(
            self._go_frame,
            text="Click tile to edit — press ENTER to start",
            font=("Menlo", 8, "bold"),
            bg=BG, fg=ORANGE,
        )
        self._hint_lbl.pack(pady=(2, 6))

        # ── progress bar text ──
        self._prog_lbl = tk.Label(root, text="", font=("Menlo", 9),
                                  bg=BG, fg=FG_DIM)
        self._prog_lbl.pack(pady=(0, 4))

        # ── word list ──
        list_hdr = tk.Frame(root, bg=BG)
        list_hdr.pack(fill="x", padx=12)
        tk.Label(list_hdr, text="#   WORD         PTS   STATUS",
                 font=("Menlo", 8), bg=BG, fg=FG_DIM).pack(anchor="w")

        canvas_frame = tk.Frame(root, bg=CARD)
        canvas_frame.pack(padx=12, pady=(2, 12), fill="both", expand=True)

        canvas = tk.Canvas(canvas_frame, bg=CARD, highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        self._word_frame = tk.Frame(canvas, bg=CARD)

        self._word_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._word_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._canvas = canvas

    # ── edit mode ─────────────────────────────────────────────────────────────

    def _show_edit_ui(self):
        self._go_frame.pack(padx=12, before=self._prog_lbl)
        self._refresh_board_edit()
        # Force the overlay window to front and grab keyboard focus
        self.root.lift()
        self.root.focus_force()

    def _hide_edit_ui(self):
        self._go_frame.pack_forget()

    def _on_tile_click(self, row, col):
        with self._lock:
            if not self._edit_mode:
                return
            self._selected_tile = (row, col)
        self._refresh_board_edit()
        self.root.focus_set()

    def _on_key(self, event):
        with self._lock:
            if not self._edit_mode:
                return
            selected = self._selected_tile

        if event.keysym == "Return":
            self._confirm_board()
            return

        ch = event.char.upper() if event.char else ""
        if ch.isalpha() and len(ch) == 1 and selected:
            r, c = selected
            with self._lock:
                self._board[r][c] = ch.lower()
                idx = r * 4 + c + 1
                if idx < 16:
                    self._selected_tile = (idx // 4, idx % 4)
                else:
                    self._selected_tile = None
            self._refresh_board_edit()

    def _confirm_board(self):
        with self._lock:
            self._edit_mode = False
            self._selected_tile = None
        self._hide_edit_ui()
        self._board_confirmed.set()

    def _refresh_board_edit(self):
        with self._lock:
            board = self._board
            selected = self._selected_tile

        if not self._board_lbls or not board:
            return

        for r in range(4):
            for c in range(4):
                lbl = self._board_lbls[r][c]
                letter = board[r][c].upper() if board else "·"
                is_error = letter == "?"

                if (r, c) == selected:
                    lbl.config(text=letter, bg=TILE_SEL, fg="#ffffff",
                               font=("Menlo", 17, "bold"))
                elif is_error:
                    lbl.config(text="?", bg=TILE_ERR, fg="#ffffff",
                               font=("Menlo", 17, "bold"))
                else:
                    lbl.config(text=letter, bg=TILE_DEF, fg=FG,
                               font=("Menlo", 17, "bold"))

    # ── word list ─────────────────────────────────────────────────────────────

    def _rebuild_word_list(self):
        if not self._word_frame:
            return
        for child in self._word_frame.winfo_children():
            child.destroy()
        self._word_rows.clear()

        with self._lock:
            words = list(self._words)

        for i, w in enumerate(words):
            row_frame = tk.Frame(self._word_frame, bg=CARD)
            row_frame.pack(fill="x", pady=1)

            num_lbl = tk.Label(row_frame, text=f"{i+1:>3}.", font=("Menlo", 9),
                               width=4, bg=CARD, fg=FG_DIM, anchor="e")
            num_lbl.pack(side="left")

            word_lbl = tk.Label(row_frame, text=f" {w['word']:<12}",
                                font=("Menlo", 9, "bold"), bg=CARD, fg=FG, anchor="w")
            word_lbl.pack(side="left")

            pts_lbl = tk.Label(row_frame, text=f"{w['points']:>5}",
                               font=("Menlo", 9), bg=CARD, fg=FG_DIM, anchor="e")
            pts_lbl.pack(side="left")

            status_lbl = tk.Label(row_frame, text="  ·  ",
                                  font=("Menlo", 9), bg=CARD, fg=FG_DIM)
            status_lbl.pack(side="left")

            self._word_rows.append({
                "frame": row_frame, "word": word_lbl,
                "status": status_lbl, "num": num_lbl,
            })

        self._refresh_word_list()

    def _refresh_word_list(self):
        with self._lock:
            current = self._current_idx
            played  = set(self._played_indices)

        for i, row in enumerate(self._word_rows):
            if i in played:
                row["frame"].config(bg=CARD)
                row["word"].config(bg=CARD, fg=FG_DIM)
                row["status"].config(text=" ✓  ", fg=GREEN, bg=CARD)
                row["num"].config(bg=CARD, fg=FG_DIM)
            elif i == current:
                row["frame"].config(bg="#1e0a14")
                row["word"].config(bg="#1e0a14", fg=ACCENT)
                row["status"].config(text=" ▶  ", fg=ACCENT, bg="#1e0a14")
                row["num"].config(bg="#1e0a14", fg=ACCENT)
                if self._canvas:
                    frac = i / max(len(self._word_rows), 1)
                    self._canvas.yview_moveto(max(0, frac - 0.1))
            else:
                row["frame"].config(bg=CARD)
                row["word"].config(bg=CARD, fg=FG)
                row["status"].config(text="  ·  ", fg=FG_DIM, bg=CARD)
                row["num"].config(bg=CARD, fg=FG_DIM)

    def _refresh_board(self):
        with self._lock:
            board = self._board
            path  = list(self._current_path)
            if self._edit_mode:
                return

        if not self._board_lbls:
            return

        path_map = {coord: i+1 for i, coord in enumerate(path)}

        for r in range(4):
            for c in range(4):
                lbl = self._board_lbls[r][c]
                letter = board[r][c].upper() if board else "·"

                if (r, c) in path_map:
                    order = path_map[(r, c)]
                    color = TILE_PATH if order == 1 else "#c0304a"
                    lbl.config(text=str(order), bg=color, fg="#ffffff",
                               font=("Menlo", 13, "bold"))
                else:
                    lbl.config(text=letter, bg=TILE_DEF, fg=FG,
                               font=("Menlo", 17, "bold"))

    def _update_loop(self):
        if not self._running:
            return

        with self._lock:
            status = self._status
            board  = self._board
            edit   = self._edit_mode

        if self._status_lbl:
            self._status_lbl.config(text=status)

        if board and not self._current_path and not edit:
            self._refresh_board()

        self.root.after(150, self._update_loop)
