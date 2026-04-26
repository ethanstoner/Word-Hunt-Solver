"""
Word Hunt solver — DFS with O(1) visited array and prefix pruning.
Supports 4x4, 5x5, Donut, and Cross board layouts (from k-gerner/Game-Pigeon-Solvers).
"""
import sys
sys.dont_write_bytecode = True

from pathlib import Path
from typing import Dict, List, Set, Tuple

# Points per word length (Game Pigeon scoring)
POINTS = {3: 100, 4: 400, 5: 800, 6: 1400, 7: 1800, 8: 2200, 9: 2600, 10: 3000}

# Board layout definitions: position_index -> (row, col)
# Donut and Cross coords from k-gerner/Game-Pigeon-Solvers
BOARD_LAYOUTS: Dict[str, List[Tuple[int, int]]] = {
    "4x4": [(r, c) for r in range(4) for c in range(4)],
    "5x5": [(r, c) for r in range(5) for c in range(5)],
    "donut": [
        # row 0 (3 tiles, cols 1-3)
        (0,1),(0,2),(0,3),
        # row 1 (5 tiles, cols 0-4)
        (1,0),(1,1),(1,2),(1,3),(1,4),
        # row 2 (4 tiles, hole at col 2)
        (2,0),(2,1),(2,3),(2,4),
        # row 3 (5 tiles, cols 0-4)
        (3,0),(3,1),(3,2),(3,3),(3,4),
        # row 4 (3 tiles, cols 1-3)
        (4,1),(4,2),(4,3),
    ],
    "cross": [
        # row 0 (4 tiles, gap at col 2)
        (0,0),(0,1),(0,3),(0,4),
        # row 1 (5 tiles, cols 0-4)
        (1,0),(1,1),(1,2),(1,3),(1,4),
        # row 2 (3 tiles, cols 1-3)
        (2,1),(2,2),(2,3),
        # row 3 (5 tiles, cols 0-4)
        (3,0),(3,1),(3,2),(3,3),(3,4),
        # row 4 (4 tiles, gap at col 2)
        (4,0),(4,1),(4,3),(4,4),
    ],
}

BOARD_SIZES = {layout: len(coords) for layout, coords in BOARD_LAYOUTS.items()}

_DIRECTIONS_8 = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]


def _build_neighbors(coords: List[Tuple[int, int]]) -> List[List[int]]:
    """Precompute 8-direction adjacency index list for a board layout."""
    coord_to_idx = {coord: i for i, coord in enumerate(coords)}
    result = []
    for r, c in coords:
        nbrs = []
        for dr, dc in _DIRECTIONS_8:
            nb = (r + dr, c + dc)
            if nb in coord_to_idx:
                nbrs.append(coord_to_idx[nb])
        result.append(nbrs)
    return result


# Precompute neighbors for all layouts once at import time
_NEIGHBORS: Dict[str, List[List[int]]] = {
    layout: _build_neighbors(coords) for layout, coords in BOARD_LAYOUTS.items()
}

# Cached dictionary (loaded once per max_length)
_dict_cache: Dict[int, Tuple[Set[str], Set[str]]] = {}


def load_dictionary(max_length: int = 10) -> Tuple[Set[str], Set[str]]:
    """Load dictionary, return (valid_words, prefixes) for DFS pruning."""
    if max_length in _dict_cache:
        return _dict_cache[max_length]

    dict_path = Path(__file__).parent.parent / "data" / "letters10.txt"
    if not dict_path.exists():
        raise FileNotFoundError(f"Dictionary not found at {dict_path}")

    words: Set[str] = set()
    prefixes: Set[str] = set()

    with open(dict_path, "r") as f:
        for line in f:
            word = line.strip().lower()
            if 3 <= len(word) <= max_length:
                words.add(word)
                for i in range(1, len(word) + 1):
                    prefixes.add(word[:i])

    _dict_cache[max_length] = (words, prefixes)
    return words, prefixes


def solve(
    letters: List[str],
    layout: str = "4x4",
    max_length: int = 10,
    max_words: int = 50,
) -> List[dict]:
    """
    Find all valid words on a Word Hunt board.

    Args:
        letters: flat list of lowercase letters matching the layout size
        layout: "4x4", "5x5", "donut", or "cross"
        max_length: max word length to search
        max_words: max results to return

    Returns:
        List of {word, path, points} sorted by points descending.
        path entries are (row, col) tuples.
    """
    if layout not in BOARD_LAYOUTS:
        raise ValueError(f"Unknown layout '{layout}'. Choose from: {list(BOARD_LAYOUTS)}")

    coords = BOARD_LAYOUTS[layout]
    neighbors = _NEIGHBORS[layout]
    n = len(coords)

    if len(letters) != n:
        raise ValueError(f"Layout '{layout}' needs {n} letters, got {len(letters)}")

    words, prefixes = load_dictionary(max_length)
    found: Dict[str, List[Tuple[int, int]]] = {}

    visited = [False] * n
    path: List[int] = []

    def dfs(idx: int, current: str) -> None:
        if current not in prefixes:
            return
        if current in words and current not in found:
            found[current] = [coords[i] for i in path]
        if len(current) >= max_length:
            return
        for nb in neighbors[idx]:
            if not visited[nb]:
                visited[nb] = True
                path.append(nb)
                dfs(nb, current + letters[nb])
                path.pop()
                visited[nb] = False

    for start in range(n):
        visited[start] = True
        path.append(start)
        dfs(start, letters[start])
        path.pop()
        visited[start] = False

    results = [
        {"word": w, "path": p, "points": POINTS.get(len(w), 3000)}
        for w, p in found.items()
    ]
    results.sort(key=lambda x: (-x["points"], -len(x["word"]), x["word"]))
    return results[:max_words]


def solve_board(board: List[List[str]], max_length: int = 10, max_words: int = 50) -> List[dict]:
    """Convenience wrapper: takes a 4x4 2D grid, returns solved words."""
    letters = [c for row in board for c in row]
    return solve(letters, layout="4x4", max_length=max_length, max_words=max_words)


def board_from_string(s: str, layout: str = "4x4") -> List[List[str]]:
    """
    Parse a letter string into a 2D board (4x4 only) or flat list (other layouts).
    For 4x4, returns List[List[str]] for backward compatibility with OCR/player code.
    For other layouts, returns a flat list wrapped in a single-item list (use .letters).
    """
    letters = s.lower().replace(" ", "")
    size = BOARD_SIZES[layout]
    if len(letters) != size:
        raise ValueError(f"Layout '{layout}' needs {size} letters, got {len(letters)}")
    if layout == "4x4":
        return [list(letters[i:i+4]) for i in range(0, 16, 4)]
    return list(letters)


if __name__ == "__main__":
    import time

    import string
    alphabet = (string.ascii_lowercase * 2)[:26]
    for layout in ["4x4", "5x5", "donut", "cross"]:
        letters = list(alphabet[:BOARD_SIZES[layout]])
        t = time.time()
        results = solve(letters, layout=layout)
        print(f"{layout}: {len(results)} words in {time.time()-t:.3f}s — top: {results[0]['word'] if results else 'none'}")
