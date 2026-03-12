import random
import time
from game_engine import PhysicsEngine
from car import CarState
from solver import AStarSolver
import settings as s

# --- CHROMOSOME CLASS ---
# A chromosome is one candidate track, stored as a 2D grid.
# The GA evolves a population of these to find solvable, interesting tracks.

class Chromosome:
    """
    Represents a single track layout as a 2D grid.
    Grid values: 0=wall, 1=road, 2=start, 3=finish
    The GA will evolve these grids until A* can solve them.
    """
    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows
        self.grid = []
        self.fitness = 0

        # Fixed positions for start and finish (bottom third, separated)
        self.start_pos = (3, rows - 4)
        self.finish_pos = (cols - 4, rows - 4)

    def random_grid(self):
        """Generate a random grid with walls on the border and random interior tiles"""
        self.grid = []
        for r in range(self.rows):
            row = []
            for c in range(self.cols):
                # Border cells are always walls (enclosed track)
                if r == 0 or r == self.rows - 1 or c == 0 or c == self.cols - 1:
                    row.append(0)
                else:
                    # 45% chance of wall, 55% road
                    row.append(0 if random.random() < 0.45 else 1)
            self.grid.append(row)

        # Stamp start and finish positions (and clear a small area around them)
        self._place_marker(self.start_pos, 2)
        self._place_marker(self.finish_pos, 3)
        return self

    def _place_marker(self, pos, value):
        """Place a start/finish marker and clear surrounding tiles to road"""
        cx, cy = pos
        # Clear a 3x3 area around the marker so the car can actually reach it
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                nx, ny = cx + dx, cy + dy
                if 0 < nx < self.cols - 1 and 0 < ny < self.rows - 1:
                    self.grid[ny][nx] = 1  #road
        # Place the actual marker in the center
        self.grid[cy][cx] = value


# --- GENETIC ALGORITHM CLASS ---

class GeneticAlgorithm:
    """
    Evolves a population of Chromosomes (track grids) using:
    - Tournament selection (pick best from random subset)
    - Single-point crossover (combine two parents)
    - Random mutation (flip tiles)
    - Elitism (always keep the best one)

    Fitness is judged by A*: can it solve the track?
    """
    def __init__(self, population_size=20, generations=35, mutation_rate=0.05):
        # Grid dimensions match the game window
        self.cols = s.screen_width // 20  #50
        self.rows = s.screen_height // 20  #40

        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate

        self.population = []
        self.fitness_history = []  #track best fitness per generation (for reports)

    # --- POPULATION ---

    def init_population(self):
        """Create initial random population"""
        self.population = []
        for _ in range(self.population_size):
            chrome = Chromosome(self.cols, self.rows)
            chrome.random_grid()
            self.population.append(chrome)
        print(f"Population initialized: {self.population_size} tracks")

    # --- FITNESS ---

    def calculate_fitness(self, chrome):
        """
        Score a track by asking A* to solve it.
        Fitness 0 = unsolvable (dead on arrival).
        Higher fitness = longer path = more interesting race.
        """
        # Build a physics engine from this chromosome's grid
        engine = PhysicsEngine(chrome.grid)
        solver = AStarSolver(engine)

        # Find start and finish on the grid
        start = chrome.start_pos
        finish = chrome.finish_pos

        # Check the tiles actually exist
        if chrome.grid[start[1]][start[0]] != 2:
            return 0
        if chrome.grid[finish[1]][finish[0]] != 3:
            return 0

        # Ask A* to find a path
        start_state = CarState(start[0], start[1], 0, 0)
        finish_coords = [(finish[0], finish[1])]

        path, _ = solver.astar_search(start_state, finish_coords)

        if path is None:
            return 0  #unsolvable = worst fitness

        # --- SCORING ---
        # Longer paths = more interesting tracks to race on
        path_score = len(path) * 10

        # Small bonus for having more road tiles (more open = more options)
        road_count = sum(1 for r in chrome.grid for tile in r if tile == 1)
        road_bonus = road_count * 0.1

        return path_score + road_bonus

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
        Single-point crossover: take top half from parent A, bottom half from parent B.
        Then re-stamp start and finish to make sure they survive.
        """
        child = Chromosome(self.cols, self.rows)
        child.grid = []

        # Split point is a random row
        split = random.randint(1, self.rows - 2)

        for r in range(self.rows):
            if r < split:
                child.grid.append(list(parent_a.grid[r]))  #copy row from A
            else:
                child.grid.append(list(parent_b.grid[r]))  #copy row from B

        # Re-stamp start and finish (crossover might have overwritten them)
        child._place_marker(child.start_pos, 2)
        child._place_marker(child.finish_pos, 3)

        return child

    # --- MUTATION ---

    def mutate(self, chrome):
        """Randomly flip tiles (wall<->road). Never touch borders, start, or finish."""
        for r in range(1, self.rows - 1):
            for c in range(1, self.cols - 1):
                if random.random() < self.mutation_rate:
                    # Don't mutate start or finish
                    if (c, r) == chrome.start_pos or (c, r) == chrome.finish_pos:
                        continue
                    # Flip: wall becomes road, road becomes wall
                    chrome.grid[r][c] = 1 if chrome.grid[r][c] == 0 else 0

    # --- EVOLUTION LOOP ---

    def run(self):
        """Main GA loop. Returns the best chromosome found."""
        print("\n=== GENETIC ALGORITHM STARTING ===")
        self.init_population()

        total_start = time.time()

        for gen in range(self.generations):
            gen_start = time.time()
            print(f"\nGeneration {gen + 1}/{self.generations}")
            self.evaluate_population()
            gen_time = time.time() - gen_start
            print(f"  Generation time: {gen_time:.2f}s")

            # Early exit if we found something great
            if self.population[0].fitness > 500:
                print("Found a strong track early! Stopping.")
                break

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
            print("WARNING: No solvable track found. Try increasing generations or road density.")

        return best
