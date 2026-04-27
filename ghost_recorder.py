"""
ghost_recorder.py
-----------------
Records the player's path through a race turn-by-turn,
"""

import hashlib
import json
import os
from datetime import datetime, timezone

GHOST_DIR       = "ghosts"
LEADERBOARD_MAX = 5
_SCHEMA_VER     = 2


# ── Track identification ──────────────────────────────────────────────────────

def track_id(grid: list[list[int]]) -> str:
    """Return a stable 10-char hex ID derived from the grid content."""
    return hashlib.md5(str(grid).encode()).hexdigest()[:10]


def _ghost_filepath(tid: str) -> str:
    os.makedirs(GHOST_DIR, exist_ok=True)
    return os.path.join(GHOST_DIR, f"ghost_{tid}.json")


# ── Timestamp helpers ─────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _now_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── Schema migration ──────────────────────────────────────────────────────────

def _migrate(old: dict, tid: str) -> dict:
    """Upgrade a v1 (flat) ghost file to the v2 schema in-place."""
    turns     = old.get("turns", 0)
    positions = old.get("positions", [])
    name      = old.get("ghost", {}).get("racer_name", "You") \
                if "ghost" in old else "You"
    return {
        "metadata": {
            "track_id":    tid,
            "schema_ver":  _SCHEMA_VER,
            "created_iso": _now_iso(),
        },
        "ghost": {
            "turns":      turns,
            "racer_name": name,
            "positions":  positions,
        },
        "leaderboard": [
            {"name": name, "turns": turns, "date": _now_date()}
        ],
    }


# ── Atomic file I/O ───────────────────────────────────────────────────────────

def _write_atomic(path: str, data: dict) -> bool:
    """Write *data* to *path* via a temp file, returning True on success."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
        return True
    except OSError as exc:
        print(f"[GHOST] Write failed for {path}: {exc}")
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False


# ── Public load / save ────────────────────────────────────────────────────────

def load_ghost(tid: str) -> dict | None:
    """
    Return the ghost dict for tid, or None if no file exists.
    
    """
    path = _ghost_filepath(tid)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[GHOST] Could not load {path}: {exc}")
        return None

    if data.get("metadata", {}).get("schema_ver", 1) < _SCHEMA_VER:
        print(f"[GHOST] Migrating {tid} to schema v{_SCHEMA_VER}")
        data = _migrate(data, tid)
        _write_atomic(path, data)

    return data


def save_ghost(tid: str,
               positions: list[tuple[int, int]],
               turns: int,
               racer_name: str = "You") -> bool:
    """
    Persist a race run for *tid*.
    Returns True if a new fastest ghost was recorded.
    """
    path     = _ghost_filepath(tid)
    existing = load_ghost(tid)
    is_new_record = False

    if existing is None:
        data = {
            "metadata": {
                "track_id":    tid,
                "schema_ver":  _SCHEMA_VER,
                "created_iso": _now_iso(),
            },
            "ghost": {
                "turns":      turns,
                "racer_name": racer_name,
                "positions":  [[x, y] for x, y in positions],
            },
            "leaderboard": [
                {"name": racer_name, "turns": turns, "date": _now_date()}
            ],
        }
        is_new_record = True
        print(f"[GHOST] First record on {tid}: {turns} turns by {racer_name}.")
    else:
        data = existing
        current_best = data.get("ghost", {}).get("turns", float("inf"))

        # Update fastest ghost
        if turns < current_best:
            data["ghost"] = {
                "turns":      turns,
                "racer_name": racer_name,
                "positions":  [[x, y] for x, y in positions],
            }
            is_new_record = True
            print(f"[GHOST] New record on {tid}: {turns} turns "
                  f"(was {current_best}) by {racer_name}.")
        else:
            print(f"[GHOST] No new record on {tid}. "
                  f"Best: {current_best}, yours: {turns}.")

        # Always append to leaderboard
        board = data.get("leaderboard", [])
        board.append({"name": racer_name, "turns": turns, "date": _now_date()})
        board.sort(key=lambda e: e["turns"])
        data["leaderboard"] = board[:LEADERBOARD_MAX]

    _write_atomic(path, data)
    return is_new_record


def get_leaderboard(tid: str) -> list[dict]:
    """Return the leaderboard for *tid*, or [] if no file exists."""
    data = load_ghost(tid)
    if data is None:
        return []
    return data.get("leaderboard", [])


def is_top5_time(tid: str, turns: int) -> bool:
    """Return True if *turns* would place in the top-5 for this track."""
    board = get_leaderboard(tid)
    if len(board) < LEADERBOARD_MAX:
        return True
    return turns < board[-1]["turns"]


# ── Live recorder ─────────────────────────────────────────────────────────────

class GhostRecorder:
    """Appends the player's grid position after each executed turn."""

    def __init__(self) -> None:
        self.positions: list[tuple[int, int]] = []

    def record(self, x: int, y: int) -> None:
        self.positions.append((x, y))

    def reset(self) -> None:
        self.positions.clear()


# ── Replay car ────────────────────────────────────────────────────────────────

class GhostCar:
    """Replays a saved ghost run as a semi-transparent overlay."""

    def __init__(self, ghost_data: dict) -> None:
        section = ghost_data.get("ghost", ghost_data)
        raw = section.get("positions", [])
        self.positions:  list[tuple[int, int]] = [(p[0], p[1]) for p in raw]
        self.best_turns: int                   = section.get("turns", 0)
        self.racer_name: str                   = section.get("racer_name", "You")

    def get_position(self, turn: int) -> tuple[int, int] | None:
        """Return ghost position at *turn*, clamped to the last known position."""
        if not self.positions:
            return None
        return self.positions[min(turn, len(self.positions) - 1)]