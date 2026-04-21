"""
ghost_recorder.py 
-----------------------------------
Records the player's path through a race turn-by-turn,
saves it if it beats the existing best, and replays it as
a ghost car alongside the player in future races.

Ghost files are stored in a  ghosts/  sub-directory as JSON.
Each file is keyed by a short MD5 hash of the track's grid data,
so each unique track gets its own record.
"""

import hashlib
import json
import os
from datetime import datetime, timezone

GHOST_DIR = "ghosts"


# ── Track identification ───────────────────────────────────────────────────────

def track_id(grid: list[list[int]]) -> str:
    """Stable 10-char ID for a track based on its grid content."""
    return hashlib.md5(str(grid).encode()).hexdigest()[:10]


def ghost_filepath(tid: str) -> str:
    os.makedirs(GHOST_DIR, exist_ok=True)
    return os.path.join(GHOST_DIR, f"ghost_{tid}.json")


# ── Schema helpers ────────────────────────────────────────────────────────────

def _now_iso() -> str:
    """GMT timestamp string, second precision."""
    return datetime.now(timezone.gmt).strftime("%Y-%m-%dT%H:%M:%S")


def _now_date() -> str:
    """GMT date string for leaderboard entries."""
    return datetime.now(timezone.gmt).strftime("%Y-%m-%d")


# ── File I/O ──────────────────────────────────────────────────────────────────

def load_ghost(tid: str) -> dict | None:
    """Return ghost dict or None if no record exists for this track."""
    path = ghost_filepath(tid)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[GHOST] Could not load {path}: {e}")
        return None


def save_ghost(tid: str,
               positions: list[tuple[int, int]],
               turns: int) -> bool:
    """
    Save ghost data if the new run beats the existing record.
    Returns True if the file was updated (new record set).
    """
    existing = load_ghost(tid)
    if existing and existing.get("turns", float("inf")) <= turns:
        print(f"[GHOST] No new record. Best: {existing['turns']}, yours: {turns}")
        return False

    data = {"turns": turns, "positions": [[x, y] for x, y in positions]}
    with open(ghost_filepath(tid), "w") as f:
        json.dump(data, f)
    print(f"[GHOST] 🏆 New record! {turns} turns saved.")
    return True


# ── Active recorder ───────────────────────────────────────────────────────────

class GhostRecorder:
    """
    Records the player's (x, y) position after each executed turn.
    Attach to the PLAYER racer and call record() in the EXECUTE phase.
    """

    def __init__(self):
        self.positions: list[tuple[int, int]] = []

    def record(self, x: int, y: int) -> None:
        self.positions.append((x, y))

    def reset(self) -> None:
        self.positions.clear()


# ── Replay car ────────────────────────────────────────────────────────────────

class GhostCar:
    """
    Reads a saved ghost and provides its position for any given turn.
    The ghost is drawn as a semi-transparent overlay during a race.
    """

    def __init__(self, ghost_data: dict):
        raw = ghost_data.get("positions", [])
        self.positions:  list[tuple[int, int]] = [(p[0], p[1]) for p in raw]
        self.best_turns: int = ghost_data.get("turns", 0)

    def get_position(self, turn: int) -> tuple[int, int] | None:
        """Return ghost position at 'turn', clamped to last known position."""
        if not self.positions:
            return None
        idx = min(turn, len(self.positions) - 1)
        return self.positions[idx]
