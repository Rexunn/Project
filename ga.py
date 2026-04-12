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
    The grid is built using Catmull-Rom splines for organic curves.
    Grid values: 0=wall, 1=road, 2=start, 3=finish, 4=checkpoint
    """
    def __init__(self, cols, rows, num_waypoints=8):
        self.cols = cols
        self.rows = rows
        self.num_waypoints = num_waypoints
        self.waypoints = []  
        self.grid = []
        self.fitness = 0
        self.start_pos = None
        self.finish_pos = None

    def random_waypoints(self):
        cx = self.cols // 2   
        cy = self.rows // 2   
        radius_x = cx - 6
        radius_y = cy - 6

        self.waypoints = []
        for i in range(self.num_waypoints):
            angle = (2 * math.pi * i) / self.num_waypoints
            wx = int(cx + radius_x * math.cos(angle)) + random.randint(-4, 4)
            wy = int(cy + radius_y * math.sin(angle)) + random.randint(-4, 4)
            wx = max(4, min(self.cols - 5, wx))
            wy = max(4, min(self.rows - 5, wy))
            self.waypoints.append((wx, wy))

        self._build_grid()
        return self

    def _build_grid(self):
        """Convert waypoints into a full grid using Catmull-Rom Splines"""
        self.grid = [[0 for _ in range(self.cols)] for _ in range(self.rows)]
        num = len(self.waypoints)

        # Carve smooth roads connecting the waypoints
        for i in range(num):
            p0 = self.waypoints[(i - 1) % num]
            p1 = self.waypoints[i]
            p2 = self.waypoints[(i + 1) % num]
            p3 = self.waypoints[(i + 2) % num]

            dist = max(abs(p2[0] - p1[0]), abs(p2[1] - p1[1]))
            steps = max(10, dist * 3)  

            for step in range(steps + 1):
                t = step / steps
                t2 = t * t
                t3 = t2 * t
                
                x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
                y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
                
                self._carve_circle(int(x), int(y), radius=2)

        # Border walls 
        for r in range(self.rows):
            self.grid[r][0] = 0
            self.grid[r][self.cols - 1] = 0
        for c in range(self.cols):
            self.grid[0][c] = 0
            self.grid[self.rows - 1][c] = 0

        # --- PLACE MARKERS ---
        sx, sy = self.waypoints[0]
        self.start_pos = (sx, sy)

        # Start/Finish lineat the very first waypoint
        self._draw_transverse_line(0, 3)

        # Start dot on the line so physics engine knows where to spawn
        self.grid[sy][sx] = 2

        # Set target to final waypoint
        fx, fy = self.waypoints[-1]
        self.finish_pos = (fx, fy)

        # Checkpoints at waypoints
        for i in range(2, len(self.waypoints) - 1, 2):
            self._draw_transverse_line(i, 4)
        
        cp_id = 1
        for i in range(2, len(self.waypoints) - 1, 2):
            self._draw_transverse_line(i, cp_id)
            cp_id += 1 # Increment for next checkpoint

    def _carve_circle(self, cx, cy, radius):
        """Uses a circular brush to paint the road"""
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx*dx + dy*dy <= radius*radius + 1: 
                    nx, ny = cx + dx, cy + dy
                    if 0 < nx < self.cols - 1 and 0 < ny < self.rows - 1:
                        if self.grid[ny][nx] == 0:  
                            self.grid[ny][nx] = 1

    def _draw_transverse_line(self, index, tile_value):
        """Draws a thin line perpendicular to the track flow until it hits a wall"""
        import math
        p_prev = self.waypoints[(index - 1) % len(self.waypoints)]
        p_next = self.waypoints[(index + 1) % len(self.waypoints)]
        curr = self.waypoints[index]

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
        
        complexity_bonus = direction_changes * 0.75  # High reward for twisty tracks

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
                wx += random.randint(-2,2)
                wy += random.randint(-2, 2)

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
