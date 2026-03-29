import random
import math
import time
from game_engine import PhysicsEngine
from car import CarState
from solver import AStarSolver
import settings as s

# --- CHROMOSOME CLASS ---
# A chromosome is a LOOP TRACK defined by waypoints.
# Waypoints sit roughly in a circle. Corridors are carved between them.
# The GA evolves waypoint positions to create varied, driveable circuits.

class Chromosome:
    """
    Represents a racing circuit as a loop of waypoints.
    The grid is built by carving wide corridors between consecutive waypoints,
    then looping the last waypoint back to the first = closed circuit.

    Grid values: 0=wall, 1=road, 2=start, 3=finish, 4=checkpoint
    """
    def __init__(self, cols, rows, num_waypoints=8):
        self.cols = cols
        self.rows = rows
        self.num_waypoints = num_waypoints
        self.waypoints = []  #list of (x, y) positions defining the loop
        self.grid = []
        self.fitness = 0
        self.start_pos = None
        self.finish_pos = None

    def random_waypoints(self):
        """
        Place waypoints in a rough circle around the center of the grid.
        Each waypoint gets a random offset so no two tracks look the same.
        """
        cx = self.cols // 2   #center x
        cy = self.rows // 2   #center y
        # Radius leaves room for border walls and corridor width
        radius_x = cx - 6
        radius_y = cy - 6

        self.waypoints = []
        for i in range(self.num_waypoints):
            # Evenly spaced angles around the circle
            angle = (2 * math.pi * i) / self.num_waypoints

            # Base position on the circle + random jitter for variety
            wx = int(cx + radius_x * math.cos(angle)) + random.randint(-4, 4)
            wy = int(cy + radius_y * math.sin(angle)) + random.randint(-4, 4)

            # Clamp inside the grid (leave room for borders + corridor width)
            wx = max(4, min(self.cols - 5, wx))
            wy = max(4, min(self.rows - 5, wy))

            self.waypoints.append((wx, wy))

        self._build_grid()
        return self

    def _build_grid(self):
        """Convert waypoints into a full grid using Catmull-Rom Splines for smooth curves"""
        self.grid = [[0 for _ in range(self.cols)] for _ in range(self.rows)]
        num = len(self.waypoints)

        # 1. Carve smooth roads connecting the waypoints
        for i in range(num):
            # We need 4 points to calculate a spline curve
            p0 = self.waypoints[(i - 1) % num]
            p1 = self.waypoints[i]
            p2 = self.waypoints[(i + 1) % num]
            p3 = self.waypoints[(i + 2) % num]

            # Estimate how many brush strokes we need based on distance
            dist = max(abs(p2[0] - p1[0]), abs(p2[1] - p1[1]))
            steps = max(10, dist * 3)  # Dense sampling so the brush strokes overlap

            for step in range(steps + 1):
                t = step / steps
                # Apply the Catmull-Rom polynomial math
                t2 = t * t
                t3 = t2 * t
                
                x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
                y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
                
                # Carve the road (radius 2 = 5 tiles wide) using the brush from Commit 1
                self._carve_circle(int(x), int(y), radius=2)

        # 2. Border walls (ensure the track is fully enclosed)
        for r in range(self.rows):
            self.grid[r][0] = 0
            self.grid[r][self.cols - 1] = 0
        for c in range(self.cols):
            self.grid[0][c] = 0
            self.grid[self.rows - 1][c] = 0

        # --- PLACE MARKERS ---
        sx, sy = self.waypoints[0]
        self.start_pos = (sx, sy)
        self.grid[sy][sx] = 2

        fx, fy = self.waypoints[-1]
        self.finish_pos = (fx, fy)
        self.grid[fy][fx] = 3

        # Place checkpoints at alternating waypoints
        for i in range(2, len(self.waypoints) - 1, 2):
            cpx, cpy = self.waypoints[i]
            self.grid[cpy][cpx] = 4

    def _carve_corridor(self, p1, p2, width=4):
        """Draw a wide road corridor from p1 to p2 using linear interpolation"""
        x1, y1 = p1
        x2, y2 = p2
        steps = max(abs(x2 - x1), abs(y2 - y1))
        if steps == 0:
            return

        half = width // 2
        for i in range(steps + 1):
            t = i / steps
            x = int(x1 + t * (x2 - x1))
            y = int(y1 + t * (y2 - y1))

            # --- NEW: Use the circular brush instead of the square one ---
            self._carve_circle(x, y, radius=half)

    def _carve_circle(self, cx, cy, radius):
        """Uses a circular brush to paint the road, eliminating blocky corners"""
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                # Standard circle formula: x^2 + y^2 <= r^2
                if dx*dx + dy*dy <= radius*radius + 1: # +1 softens the edge slightly
                    nx, ny = cx + dx, cy + dy
                    # Stay inside borders
                    if 0 < nx < self.cols - 1 and 0 < ny < self.rows - 1:
                        if self.grid[ny][nx] == 0:  # Only overwrite walls
                            self.grid[ny][nx] = 1


# --- GENETIC ALGORITHM CLASS ---

class GeneticAlgorithm:
    """
    Evolves a population of loop-track Chromosomes using:
    - Tournament selection (pick best from random subset)
    - Uniform crossover (mix waypoints from two parents)
    - Waypoint mutation (shift waypoints to create meanders)
    - Elitism (always keep the best one)

    Fitness is judged by A*: can it complete the full circuit?
    """
    def __init__(self, population_size=20, generations=35, mutation_rate=0.3):
        # Grid dimensions match the game window
        self.cols = s.screen_width // 20  #50
        self.rows = s.screen_height // 20  #40

        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate  #chance of shifting each waypoint

        self.population = []
        self.fitness_history = []  #track best fitness per generation (for reports)

    # --- POPULATION ---

    def init_population(self):
        """Create initial random population of loop tracks"""
        self.population = []
        for _ in range(self.population_size):
            chrome = Chromosome(self.cols, self.rows)
            chrome.random_waypoints()
            self.population.append(chrome)
        print(f"Population initialized: {self.population_size} loop tracks")

    # --- FITNESS ---

    def calculate_fitness(self, chrome):
        """
        LIGHTWEIGHT fitness check: just test start->finish with a single A* call.
        The full checkpoint pipeline (solve()) is only used once on the winning track.
        This keeps the GA fast — hundreds of evaluations per run.
        """
        engine = PhysicsEngine(chrome.grid)
        solver = AStarSolver(engine)

        start = chrome.start_pos
        finish = chrome.finish_pos
        if start is None or finish is None:
            return 0

        # Check the tiles actually exist on the grid
        if chrome.grid[start[1]][start[0]] != 2:
            return 0
        if chrome.grid[finish[1]][finish[0]] != 3:
            return 0

        # Single A* call: can we get from start to finish?
        start_state = CarState(start[0], start[1], 0, 0)
        finish_coords = [(finish[0], finish[1])]
        path, _ = solver.astar_search(start_state, finish_coords)

        if path is None or len(path) < 3:
            return 0  #unsolvable or trivially short

       # --- SCORING ---
        # 1. Base Score: Longer path = the circuit forces the car to travel further
        path_score = len(path) * 10

        # 2. Complexity Bonus: Count how many times the car changes direction/speed
        direction_changes = 0
        for i in range(1, len(path)):
            prev_state = path[i - 1]
            curr_state = path[i]
            # If the velocity vector changes, the AI had to steer, brake, or accelerate
            if prev_state.vx != curr_state.vx or prev_state.vy != curr_state.vy:
                direction_changes += 1
        
        complexity_bonus = direction_changes * 15  # High reward for twisty tracks

        # 3. Size Bonus: Total road area (more road = wider/longer corridors)
        road_count = sum(1 for r in chrome.grid for t in r if t >= 1)
        road_bonus = road_count * 0.3

        return path_score + complexity_bonus + road_bonus

    def evaluate_population(self):
        """Score every chromosome in the population"""
        solvable = 0
        for chrome in self.population:
            chrome.fitness = self.calculate_fitness(chrome)
            if chrome.fitness > 0:
                solvable += 1

        # Sort by fitness (best first)
        self.population.sort(key=lambda c: c.fitness, reverse=True)
        best = self.population[0].fitness
        self.fitness_history.append(best)

        print(f"  Best fitness: {best:.1f} | Solvable: {solvable}/{self.population_size}")

    # --- SELECTION ---

    def tournament_select(self, tournament_size=3):
        """Pick the best chromosome from a random subset of the population"""
        contestants = random.sample(self.population, tournament_size)
        contestants.sort(key=lambda c: c.fitness, reverse=True)
        return contestants[0]

    # --- CROSSOVER ---

    def crossover(self, parent_a, parent_b):
        """
        Uniform crossover: for each waypoint, randomly pick from parent A or B.
        Then rebuild the grid from the mixed waypoints.
        """
        child = Chromosome(self.cols, self.rows)
        child.waypoints = []

        for i in range(parent_a.num_waypoints):
            # 50/50 chance of inheriting from either parent
            if random.random() < 0.5:
                child.waypoints.append(parent_a.waypoints[i])
            else:
                child.waypoints.append(parent_b.waypoints[i])

        child._build_grid()
        return child

    # --- MUTATION ---

    def mutate(self, chrome):
        """Shift random waypoints by a few tiles to create meanders and variation"""
        changed = False
        for i in range(len(chrome.waypoints)):
            if random.random() < self.mutation_rate:
                wx, wy = chrome.waypoints[i]

                # Random shift of 1-5 tiles in any direction
                wx += random.randint(-5, 5)
                wy += random.randint(-5, 5)

                # Clamp inside grid
                wx = max(4, min(self.cols - 5, wx))
                wy = max(4, min(self.rows - 5, wy))

                chrome.waypoints[i] = (wx, wy)
                changed = True

        # Rebuild the grid if any waypoints moved
        if changed:
            chrome._build_grid()

    # --- EVOLUTION LOOP ---

    def run(self, update_callback=None):
        """Main GA loop. Returns the best chromosome found."""
        print("\n=== GENETIC ALGORITHM STARTING ===")
        self.init_population()

        total_start = time.time()

        for gen in range(self.generations):
            gen_start = time.time()
            print(f"\nGeneration {gen + 1}/{self.generations}")
            self.evaluate_population()

            # Trigger live graph drawing
            if update_callback:
                update_callback(gen + 1, self.generations, self.fitness_history)

            gen_time = time.time() - gen_start
            print(f"  Generation time: {gen_time:.2f}s")

            # --- BUILD NEXT GENERATION ---
            next_gen = []

            # Elitism: keep the best one unchanged
            next_gen.append(self.population[0])

            # Fill the rest with offspring
            while len(next_gen) < self.population_size:
                parent_a = self.tournament_select()
                parent_b = self.tournament_select()
                child = self.crossover(parent_a, parent_b)
                self.mutate(child)
                next_gen.append(child)

            self.population = next_gen

        # Final evaluation to make sure we return the true best
        self.evaluate_population()
        best = self.population[0]

        total_time = time.time() - total_start
        print(f"\n=== GA COMPLETE ===")
        print(f"Best fitness: {best.fitness:.1f}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Fitness history: {[f'{f:.0f}' for f in self.fitness_history]}")

        if best.fitness == 0:
            print("WARNING: No solvable track found. Try increasing generations.")

        return best
