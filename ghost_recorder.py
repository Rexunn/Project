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

def _migrate_old_schema(old: dict, tid: str) -> dict:
    """
    Convert a flat-schema ghost file to the new three-section format
    Old format:  {"turns": N, "positions": [[x,y], ...]}
    New format:  {"metadata": {...}, "ghost": {...}, "leaderboard": [...]}
    """
    turns     = old.get("turns", 0)
    positions = old.get("positions", [])

    return {
        "metadata": {
            "track_id":    tid,
            "created_iso": _now_iso(),
        },
        "ghost": {
            "turns":     turns,
            "positions": positions,
        },
        "leaderboard": [
            {"name": "You", "turns": turns, "date": _now_date()}
        ],
    }

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
    
    if "metadata" not in data:
        print(f"[GHOST] Migrating old schema for track {tid}")
        data = _migrate_old_schema(data, tid)
        # Write migrated file immediately so future loads use new schema
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"[GHOST] Migration write failed: {e}")

    return data


def save_ghost(tid: str,
               positions: list[tuple[int, int]],
               turns: int, racer_name="You") -> bool:
    """
    Save ghost data if the new run beats the existing record.
    Returns True if the file was updated (new record set).
    """
    existing = load_ghost(tid)
    is_new_record = False

    if existing is None:
        # First ever run on this track — create a fresh file
        data = {
            "metadata": {
                "track_id":    tid,
                "created_iso": _now_iso(),
            },
            "ghost": {
                "turns":     turns,
                "positions": [[x, y] for x, y in positions],
                "racer_name": racer_name,
            },
            "leaderboard": [
                {"name": racer_name, "turns": turns, "date": _now_date()}
            ],
        }
        is_new_record = True
        print(f"[GHOST] First record on this track: {turns} turns.")

    else:
        data = existing

        # ── 1. Ghost update ───────────────────────────────────────────────────
        current_best = data.get("ghost", {}).get("turns", float("inf"))
        if turns < current_best:
            data["ghost"] = {
                "turns":     turns,
                "positions": [[x, y] for x, y in positions],
            }
            is_new_record = True
            print(f"[GHOST] New record: {turns} turns (was {current_best}).")
        else:
            print(f"[GHOST] No new record. Best: {current_best}, yours: {turns}.")

        # ── 2. Leaderboard update ─────────────────────────────────────────────
        board = data.get("leaderboard", [])
        board.append({"name": racer_name, "turns": turns, "date": _now_date()})
        board.sort(key=lambda e: e["turns"])
        data["leaderboard"] = board[:LEADERBOARD_MAX]

    # Write atomically via a temp file to avoid corruption on crash
    path     = ghost_filepath(tid)
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)
    except IOError as e:
        print(f"[GHOST] Write failed: {e}")

    return is_new_record

def get_leaderboard(tid: str) -> list:
    """
    Return the leaderboard list for this track, or [] if no file exists.

    dict: {"name": str, "turns": int, "date": str}.
    """
    data = load_ghost(tid)
    if data is None:
        return []
    return data.get("leaderboard", [])


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
        ghost_section = ghost_data.get("ghost", ghost_data)
        raw = ghost_section.get("positions", [])
        self.positions:  list[tuple[int, int]] = [(p[0], p[1]) for p in raw]
        self.best_turns: int = ghost_section.get("turns", 0)

    def get_position(self, turn: int) -> tuple[int, int] | None:
        """Return ghost position at 'turn', clamped to last known position."""
        if not self.positions:
            return None
        return self.positions[min(turn, len(self.positions) - 1)]
