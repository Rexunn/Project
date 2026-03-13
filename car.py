class CarState:
    """
    Stores the snapshot of a car at a specific moment (Discrete State).
    Used for the A* Algorithm to remember where it has been.
    """
    def __init__(self, x, y, vx, vy):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy

    #tells Python how to check if two states are the same
    def __eq__(self, other):
        return (self.x, self.y, self.vx, self.vy) == (other.x, other.y, other.vx, other.vy)

    #allows object to be put into a Set or Dictionary
    def __hash__(self):
        return hash((self.x, self.y, self.vx, self.vy))

    #helper for debugging
    def __repr__(self):
        return f"Car(x={self.x}, y={self.y}, vx={self.vx}, vy={self.vy})"
    

    def __lt__(self, other):
        return False  # don't care which car comes first if scores are equal


# --- RACER CLASS ---
# Wraps a CarState with racing-specific info.
# CarState stays immutable for A*, Racer handles the game logic.

class Racer:
    """
    A car in a race. Wraps CarState and adds:
    - Color and name (for drawing)
    - Type (PLAYER, CPU_EASY, CPU_MEDIUM, CPU_HARD)
    - Checkpoint progress tracking
    - Race status (finished, crashed)
    """
    def __init__(self, state, color, racer_type, name):
        self.state = state              #current CarState
        self.color = color
        self.type = racer_type          # "PLAYER", "CPU_EASY", "CPU_MEDIUM", "CPU_HARD"
        self.name = name

        # Race progress
        self.checkpoints_cleared = set()  #indices of checkpoint clusters hit
        self.finished = False
        self.crashed = False

        # CPU_HARD pre-computed path
        self.precomputed_path = []
        self.path_index = 0