"""
obstacles
------------
Obstacle data model and procedural placement

Two types:
  OilSpill  — contact randomises player acceleration for OIL_SLICK_TURNS turns.
  Pothole   — contact costs the player one life and triggers a respawn
              (same consequence as hitting a wall with lives remaining).

Only the player is affected.  CPU racers pass over obstacles without penalty.
Obstacles are placed on plain road tiles (grid value 1) and regenerated each
time a new race begins
"""

import random
import settings as s


class Obstacle:
    """A single track hazard at grid coordinate (x, y)."""

    def __init__(self, obs_type: str, x: int, y: int):
        self.type:   str  = obs_type   # "OilSpill" | "Pothole"
        self.x:      int  = x
        self.y:      int  = y
        # Potholes become inactive once triggered so they can only be hit once.
        # Oil spills remain active (player can skid through them repeatedly).
        self.active: bool = True

    def __repr__(self) -> str:
        return f"Obstacle({self.type!r}, x={self.x}, y={self.y})"

def _footprint_safe(track_grid: list, cx: int, cy: int) -> bool:
    """
    Return True if every tile in the 3×3 region centred on (cx, cy) is a
    plain road tile (value == 1).

    """
    rows = len(track_grid)
    cols = len(track_grid[0]) if rows else 0
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            nx, ny = cx + dx, cy + dy
            if nx < 0 or nx >= cols or ny < 0 or ny >= rows:
                return False
            if track_grid[ny][nx] != 1:
                return False
    return True


def generate_obstacles(track_grid: list, n: int | None = None) -> list:
    """
    Randomly place N obstacles on plain road tiles.


    Returns a list of Obstacle objects ready to use immediately.
    """
    if n is None:
        n = s.OBSTACLE_COUNT

    rows = len(track_grid)
    cols = len(track_grid[0]) if rows else 0

    eligible = [
        (c, r)
        for r in range(rows)
        for c in range(cols)
        if track_grid[r][c] == 1
    ]

    if not eligible:
        return []

    random.shuffle(eligible)
    chosen = eligible[:min(n, len(eligible))]

    return [
        Obstacle(random.choice(s.OBSTACLE_TYPES), x, y)
        for x, y in chosen
    ]