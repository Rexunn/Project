import settings as s


class CarState:
    """
    Immutable snapshot of a car at one moment in time.
    Used by A* as the search node — must be hashable and comparable.
    """
    def __init__(self, x, y, vx, vy):
        self.x  = x;  self.y  = y
        self.vx = vx; self.vy = vy

    def __eq__(self, other):
        return (self.x, self.y, self.vx, self.vy) == \
               (other.x, other.y, other.vx, other.vy)

    def __hash__(self):
        return hash((self.x, self.y, self.vx, self.vy))

    def __repr__(self):
        return f"Car(x={self.x}, y={self.y}, vx={self.vx}, vy={self.vy})"

    def __lt__(self, other):
        return False   # tie-break in PriorityQueue — order doesn't matter


class Racer:
    """
    A car competing in the race.


    """

    def __init__(self, state: CarState, color, racer_type: str, name: str):
        self.state      = state
        self.color      = color
        self.type       = racer_type   # "PLAYER" | "CPU_EASY" | "CPU_MEDIUM" | "CPU_HARD"
        self.name       = name

        # ── Race progress ────────────────────────────────────────────────────
        self.checkpoints_cleared: set  = set()
        self.finished: bool  = False
        self.crashed:  bool  = False
        self.finish_turn: int | None = None

        self.grace_turns_remaining: int = 0
        self.wrong_way: bool = False
        self.last_checkpoint_pos: "CarState" | None = None

        # ── Lap tracking ─────────────────────────────────────────────────────
        self.laps_completed: int = 0
        self.total_laps:     int = 1

        # ── Lives — 3 for player, irrelevant for CPUs ────────────
        self.lives:     int = s.PLAYER_LIVES if racer_type == "PLAYER" else 1
        self.max_lives: int = s.PLAYER_LIVES if racer_type == "PLAYER" else 1

        # ── Ghost recording ───────────────────────────────────────
        # Player's position is appended here every turn during RUNNING.
        self.ghost_positions: list[tuple[int, int]] = []

       

        # ── CPU Hard pre-computed path ────────────────────────────────────────
        self.precomputed_path: list[CarState] = []
        self.path_index:       int            = 0
        self.explored_states:  list[CarState] = []
        self.solve_time:       float          = 0.0

        # ── Checkpoint respawn ───────────────────────────────────────────
        # Centroid of the last checkpoint cluster the racer crossed.
        # None means fall back to the race start_state.
        self.last_checkpoint_pos: tuple[int, int] | None = None

        # ── Movement trail ───────────────────────────────────────────────
        # Ring buffer of recent (x, y) grid positions, newest at the end.
        self.trail_positions: list[tuple[int, int]] = []