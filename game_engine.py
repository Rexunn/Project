"""
game_engine.py
--------------
Discrete grid physics.
"""

import settings as s
from car import CarState


class PhysicsEngine:

    def __init__(self, track_grid, weather: str = "Sunny"):
        self.track = track_grid
        self.rows  = len(track_grid)
        self.cols  = len(track_grid[0])
        self.lethal_tiles = {0}
        self.set_weather(weather)

    # ── Weather ───────────────────────────────────────────────────────────────

    def set_weather(self, weather: str) -> None:
        """Hot-swap weather without rebuilding the engine instance."""
        self.weather = weather
        params = s.WEATHER_PHYSICS.get(weather, s.WEATHER_PHYSICS["Sunny"])
        self.max_speed   = params["max_speed"]
        self.accel_limit = params["accel_limit"]
        self.brake_limit = params["brake_limit"]

    # ── Legal move generation ─────────────────────────────────────────────────

    def get_legal_moves(self, current_state: CarState) -> list:
        moves = []
        accel_range = range(-self.accel_limit, self.accel_limit + 1)

        for ax in accel_range:
            for ay in accel_range:

                # Snowy: cap hard-braking against current velocity
                if self.weather == "Snowy":
                    # ax is braking if it opposes vx
                    if current_state.vx != 0 and ax != 0:
                        if ax * current_state.vx < 0 and abs(ax) > self.brake_limit:
                            continue
                    if current_state.vy != 0 and ay != 0:
                        if ay * current_state.vy < 0 and abs(ay) > self.brake_limit:
                            continue

                new_vx = current_state.vx + ax
                new_vy = current_state.vy + ay

                # Velocity cap
                new_vx = max(-self.max_speed, min(self.max_speed, new_vx))
                new_vy = max(-self.max_speed, min(self.max_speed, new_vy))

                new_x = current_state.x + new_vx
                new_y = current_state.y + new_vy

                if self._check_path(current_state.x, current_state.y,
                                    new_x, new_y):
                    moves.append(CarState(new_x, new_y, new_vx, new_vy))

        return moves

    # ── Path / safety ─────────────────────────────────────────────────────────

    def _check_path(self, x1, y1, x2, y2) -> bool:
        """Bresenham line — prevents tunnelling through walls."""
        if not self._is_safe(x2, y2):
            return False
        dx    = abs(x2 - x1)
        dy    = abs(y2 - y1)
        steps = max(dx, dy)
        if steps == 0:
            return True
        for i in range(1, steps + 1):
            t  = i / steps
            xt = int(x1 + t * (x2 - x1))
            yt = int(y1 + t * (y2 - y1))
            if not self._is_safe(xt, yt):
                return False
        return True

    def _is_safe(self, x, y) -> bool:
        if x < 0 or x >= self.cols or y < 0 or y >= self.rows:
            return False
        return self.track[y][x] not in self.lethal_tiles

    def get_crossed_tiles(self, x1: int, y1: int, x2: int, y2: int) -> list[tuple[int, int]]:
        """
        Bresenham's Line Algorithm.
        Returns every (x, y) grid tile crossed when moving from (x1,y1) to (x2,y2)
        continuous collision detection — prevents tunnelling through
        checkpoints and finish lines at high velocity.
        """
        tiles = []
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        x, y = x1, y1
        sx = 1 if x2 > x1 else -1
        sy = 1 if y2 > y1 else -1

        if dx > dy:
            err = dx / 2
            while x != x2:
                x += sx
                err -= dy
                if err < 0:
                    y += sy
                    err += dx
                tiles.append((x, y))
        else:
            err = dy / 2
            while y != y2:
                y += sy
                err -= dx
                if err < 0:
                    x += sx
                    err += dy
                tiles.append((x, y))

        # Ensure destination is always included
        if not tiles or tiles[-1] != (x2, y2):
            tiles.append((x2, y2))

        return tiles