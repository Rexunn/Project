import random
import math
import time
from game_engine import PhysicsEngine
from car import CarState
from solver import AStarSolver
import settings as s

# ─────────────────────────────────────────────────────────────────────────────
# CHROMOSOME
# ─────────────────────────────────────────────────────────────────────────────

class Chromosome:
    """
    A racing circuit defined by a loop of waypoints.
    The grid is built from those waypoints using Catmull-Rom splines.

    accepts carve_radius and jitter from the GA sharpness preset
    so the track shape reflects the user's selection on the GA_SETUP screen.

    Grid values: 0=wall, 1=road, 2=start, 3=finish, 4=checkpoint
    """

    def __init__(self, cols: int, rows: int,
                 num_waypoints: int = 10,
                 carve_radius:  int = 2,
                 jitter:        int = 2):
        self.cols          = cols
        self.rows          = rows
        self.num_waypoints = num_waypoints
        self.carve_radius  = carve_radius   # road-corridor width
        self.jitter        = jitter         # per-waypoint random offset
        self.waypoints: list   = []
        self.grid:      list   = []
        self.fitness:   float  = 0
        self.start_pos         = None
        self.finish_pos        = None

    def random_waypoints(self):
        cx = self.cols // 2
        cy = self.rows // 2
        rx = cx - 6
        ry = cy - 6

        self.waypoints = []
        for i in range(self.num_waypoints):
            angle = (2 * math.pi * i) / self.num_waypoints
            wx = int(cx + rx * math.cos(angle)) + random.randint(-self.jitter, self.jitter)
            wy = int(cy + ry * math.sin(angle)) + random.randint(-self.jitter, self.jitter)
            wx = max(4, min(self.cols - 5, wx))
            wy = max(4, min(self.rows - 5, wy))
            self.waypoints.append((wx, wy))

        self._build_grid()
        return self

    def _build_grid(self):
        """Convert waypoints into a full grid using Catmull-Rom splines."""
        self.grid = [[0] * self.cols for _ in range(self.rows)]
        num = len(self.waypoints)

        for i in range(num):
            p0 = self.waypoints[(i - 1) % num]
            p1 = self.waypoints[i]
            p2 = self.waypoints[(i + 1) % num]
            p3 = self.waypoints[(i + 2) % num]

            dist  = max(abs(p2[0] - p1[0]), abs(p2[1] - p1[1]))
            steps = max(10, dist * 3)

            last_drawn = None

            for step in range(steps + 1):
                t  = step / steps
                t2 = t * t
                t3 = t2 * t
                x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                            + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                            + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
                y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                            + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                            + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
                ix, iy = int(x), int(y)
                if (ix, iy) != last_drawn:
                    self._carve_circle(ix, iy, radius=self.carve_radius)
                    last_drawn = (ix, iy)
                
        # Border walls
        for r in range(self.rows):
            self.grid[r][0] = self.grid[r][self.cols - 1] = 0
        for c in range(self.cols):
            self.grid[0][c] = self.grid[self.rows - 1][c] = 0

        # Place markers
        sx, sy = self.waypoints[0]
        self.start_pos = (sx, sy)
        self._draw_transverse_line(0, 3)   # start/finish line
        self.grid[sy][sx] = 2              # start spawn dot

        fx, fy = self.waypoints[-1]
        self.finish_pos = (fx, fy)

       # ── Checkpoint placement: sort and slice by local curvature
        candidates = list(range(2, len(self.waypoints) - 1, 2))

        # Score each candidate; pair with its waypoint index for re-sorting.
        scored = sorted(
            [(self._curvature_score(i), i) for i in candidates]
        )   # ascending: index 0 is the flattest (best) candidate

        # How many checkpoints to place. At least 2, at most all candidates.
        n_checkpoints = max(2, math.ceil(len(candidates) / 2))

        # Take the n_checkpoints flattest candidates, then restore circuit order.
        chosen = sorted(idx for _, idx in scored[:n_checkpoints])

        # Draw in index order — this preserves the circuit sequence so the
        # solver and wrong-way vectors remain consistent.
        cp_id = 4
        for i in sorted(chosen):
            self._draw_transverse_line(i, cp_id)
            cp_id += 1

    def _carve_circle(self, cx: int, cy: int, radius: int) -> None:
        """Circular brush — road corridor width controlled by radius."""
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius + 1:
                    nx, ny = cx + dx, cy + dy
                    if 0 < nx < self.cols - 1 and 0 < ny < self.rows - 1:
                        if self.grid[ny][nx] == 0:
                            self.grid[ny][nx] = 1

    def _draw_transverse_line(self, index: int, tile_value: int) -> None:
        """Draw a line perpendicular to the track flow at waypoint[index]."""
        p_prev = self.waypoints[(index - 1) % len(self.waypoints)]
        p_next = self.waypoints[(index + 1) % len(self.waypoints)]
        curr   = self.waypoints[index]
        dx = p_next[0] - p_prev[0]
        dy = p_next[1] - p_prev[1]
        length = max(0.0001, math.hypot(dx, dy))
        nx, ny = -dy / length, dx / length
        for direction in [1, -1]:
            for step in range(10):
                cx = int(curr[0] + nx * step * direction)
                cy = int(curr[1] + ny * step * direction)
                if 0 < cx < self.cols - 1 and 0 < cy < self.rows - 1:
                    if self.grid[cy][cx] == 1:
                        self.grid[cy][cx] = tile_value
                    elif self.grid[cy][cx] == 0:
                        break
    def _curvature_score(self, idx: int) -> float:
        """
        Curvature score for waypoint[idx].

        Computed as (1 - dot(incoming_tangent, outgoing_tangent)), where
        both tangent vectors are unit-length.

        Interpretation
        --------------
        0.0  → perfectly straight section  (ideal checkpoint location)
        1.0  → 90-degree corner
        2.0  → complete U-turn / reversal   (worst possible location)

        A threshold of ~1.2 rejects anything tighter than ~115 degrees,
        which matches the kinds of hairpin apexes that cause ambiguous
        forward vectors in the wrong-way dot-product check.
        """
        prev = self.waypoints[(idx - 1) % len(self.waypoints)]
        curr = self.waypoints[idx]
        nxt  = self.waypoints[(idx + 1) % len(self.waypoints)]

        # Incoming and outgoing direction vectors
        dx1, dy1 = curr[0] - prev[0], curr[1] - prev[1]
        dx2, dy2 = nxt[0]  - curr[0], nxt[1]  - curr[1]

        len1 = max(0.001, math.hypot(dx1, dy1))
        len2 = max(0.001, math.hypot(dx2, dy2))

        dot = (dx1 / len1) * (dx2 / len2) + (dy1 / len1) * (dy2 / len2)
        return 1.0 - dot   # range [0, 2], lower = straighter


# ─────────────────────────────────────────────────────────────────────────────
# GENETIC ALGORITHM
# ─────────────────────────────────────────────────────────────────────────────

class GeneticAlgorithm:
    """
    Evolves a population of loop-track Chromosomes.

    accepts num_waypoints and sharpness from the GA_SETUP screen.
    These are forwarded to every Chromosome created during init and crossover.
    The sharpness preset also controls the mutation variance in mutate().
    """

    def __init__(self,
                 population_size: int  = 20,
                 generations:     int  = 35,
                 mutation_rate:   float = 0.3,
                 num_waypoints:   int  = 6,        
                 sharpness:       str  = "Normal"  # 
                 ):
        self.cols = s.screen_width  // 20
        self.rows = s.screen_height // 20

        self.population_size = population_size
        self.generations     = generations
        self.mutation_rate   = mutation_rate

        #store GA shape parameters
        self.num_waypoints = num_waypoints
        self.sharpness     = sharpness
        preset = s.GA_SHARPNESS_PRESETS.get(sharpness,
                                             s.GA_SHARPNESS_PRESETS["Normal"])
        self.carve_radius = preset["carve_radius"]
        self.mut_variance = preset["mut_variance"]
        self.jitter       = preset["jitter"]

        self.population:       list  = []
        self.fitness_history:  list  = []

    # ── Population ────────────────────────────────────────────────────────────

    def _new_chromosome(self) -> Chromosome:
        """Create a Chromosome configured with the current GA parameters."""
        return Chromosome(
            self.cols, self.rows,
            num_waypoints=self.num_waypoints,
            carve_radius=self.carve_radius,
            jitter=self.jitter,
        )

    def init_population(self):
        self.population = []
        for _ in range(self.population_size):
            ch = self._new_chromosome()
            ch.random_waypoints()
            self.population.append(ch)
        print(f"Population: {self.population_size} tracks  "
              f"| waypoints={self.num_waypoints}  sharpness={self.sharpness}")

    # ── Fitness ───────────────────────────────────────────────────────────────

    def calculate_fitness(self, chrome: Chromosome) -> float:
        engine = PhysicsEngine(chrome.grid)
        solver = AStarSolver(engine)

        start  = chrome.start_pos
        finish = chrome.finish_pos
        if start is None or finish is None:
            return 0
        if chrome.grid[start[1]][start[0]] != 2:
            return 0

        start_state   = CarState(start[0], start[1], 0, 0)
        finish_coords = [(finish[0], finish[1])]
        path, _       = solver.astar_search(start_state, finish_coords)

        if path is None or len(path) < 3:
            return 0

        path_score = len(path) * 10

        direction_changes = sum(
            1 for i in range(1, len(path))
            if path[i - 1].vx != path[i].vx or path[i - 1].vy != path[i].vy
        )
        complexity_bonus = direction_changes * 1.25

        road_count = sum(1 for r in chrome.grid for t in r if t >= 1)
        road_bonus = road_count * 0.3

        return path_score + complexity_bonus + road_bonus

    def evaluate_population(self):
        solvable = 0
        for ch in self.population:
            ch.fitness = self.calculate_fitness(ch)
            if ch.fitness > 0:
                solvable += 1
        self.population.sort(key=lambda c: c.fitness, reverse=True)
        best = self.population[0].fitness
        self.fitness_history.append(best)
        print(f"  Best fitness: {best:.1f} | Solvable: {solvable}/{self.population_size}")

    # ── Selection / Crossover / Mutation ──────────────────────────────────────

    def tournament_select(self, tournament_size: int = 3) -> Chromosome:
        contestants = random.sample(self.population, tournament_size)
        return max(contestants, key=lambda c: c.fitness)

    def crossover(self, parent_a: Chromosome, parent_b: Chromosome) -> Chromosome:
        """Uniform crossover: mix waypoints from two parents."""
        child = self._new_chromosome()
        child.waypoints = [
            parent_a.waypoints[i] if random.random() < 0.5
            else parent_b.waypoints[i]
            for i in range(self.num_waypoints)
        ]
        child._build_grid()
        return child

    def mutate(self, chrome: Chromosome) -> None:
        """
        Shift waypoints by a random amount.
        """
        changed = False
        for i in range(len(chrome.waypoints)):
            if random.random() < self.mutation_rate:
                wx, wy = chrome.waypoints[i]
                wx += random.randint(-self.mut_variance, self.mut_variance)
                wy += random.randint(-self.mut_variance, self.mut_variance)
                wx = max(4, min(self.cols - 5, wx))
                wy = max(4, min(self.rows - 5, wy))
                chrome.waypoints[i] = (wx, wy)
                changed = True
        if changed:
            chrome._build_grid()

    # ── Evolution loop ────────────────────────────────────────────────────────

    def run(self, update_callback=None) -> Chromosome:
        print(f"\n=== GA STARTING  waypoints={self.num_waypoints}"
              f"  sharpness={self.sharpness} ===")
        self.init_population()
        total_start = time.time()

        for gen in range(self.generations):
            gen_start = time.time()
            print(f"\nGeneration {gen + 1}/{self.generations}")
            self.evaluate_population()

            if update_callback:
                update_callback(gen + 1, self.generations, self.fitness_history)

            print(f"  Generation time: {time.time() - gen_start:.2f}s")

            next_gen = [self.population[0]]   # elitism
            while len(next_gen) < self.population_size:
                child = self.crossover(self.tournament_select(),
                                       self.tournament_select())
                self.mutate(child)
                next_gen.append(child)
            self.population = next_gen

        self.evaluate_population()
        best       = self.population[0]
        total_time = time.time() - total_start
        print(f"\n=== GA COMPLETE  best={best.fitness:.1f}  time={total_time:.2f}s ===")

        if best.fitness == 0:
            print("WARNING: No solvable track found.")
        return best