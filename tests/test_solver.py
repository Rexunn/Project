"""
tests/test_solver.py
--------------------
Unit test suite for Chapter 6.

Run from project root:
    python -m pytest tests/test_solver.py -v

All tests are self-contained and headless (no Pygame window required).
"""

import os, sys
import pytest

# ── Headless Pygame setup (must precede any game import) ─────────────────────
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()   # safe with dummy driver — no window created

from car import CarState
from game_engine import PhysicsEngine
from solver import AStarSolver, OrderedCarState
from game_state_manager import GameState, GameStateManager
from obstacles import generate_obstacles
from ga import GeneticAlgorithm, Chromosome


# ═══════════════════════════════════════════════════════════════════════════════
# Shared fixtures
# ═══════════════════════════════════════════════════════════════════════════════

def _make_oval_grid():
    """
    10×8 grid containing a simple clockwise oval:
      - road tiles (1) form a ring
      - start tile (2) at (2,1)
      - finish tile (3) at (7,1)
      - one checkpoint cluster (4) at column 4, rows 1-2

    Grid layout (columns left→right, rows top→bottom):
      0 0 0 0 0 0 0 0 0 0
      0 2 1 1 4 1 1 3 1 0
      0 1 0 0 4 0 0 1 0 0   ← inner walls
      0 1 0 0 0 0 0 1 0 0
      0 1 0 0 0 0 0 1 0 0
      0 1 0 0 0 0 0 1 0 0
      0 1 1 1 1 1 1 1 0 0
      0 0 0 0 0 0 0 0 0 0
    """
    rows, cols = 8, 10
    g = [[0]*cols for _ in range(rows)]
    # top corridor
    for c in range(1, 9):
        g[1][c] = 1
    g[1][2] = 2   # start
    g[1][7] = 3   # finish
    g[1][4] = 4   # checkpoint col
    g[2][4] = 4
    # side corridors
    for r in range(1, 7):
        g[r][1] = 1
        g[r][7] = 1
    # bottom corridor
    for c in range(1, 8):
        g[6][c] = 1
    return g


def _oval_engine(weather="Sunny"):
    grid   = _make_oval_grid()
    engine = PhysicsEngine(grid, weather=weather)
    return engine, grid


def _oval_solver(weather="Sunny"):
    engine, grid = _oval_engine(weather)
    return AStarSolver(engine), engine, grid


# ═══════════════════════════════════════════════════════════════════════════════
# UT-01  Legal moves never exceed max_speed in any weather mode
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("weather,expected_max", [
    ("Sunny", 5),
    ("Rainy", 3),
    ("Snowy", 4),
])
def test_legal_moves_respect_max_speed(weather, expected_max):
    """UT-01: No successor state has |vx| or |vy| > max_speed for any weather."""
    engine, _ = _oval_engine(weather)
    start     = CarState(2, 1, 0, 0)
    violations = 0
    for move in engine.get_legal_moves(start):
        if abs(move.vx) > expected_max or abs(move.vy) > expected_max:
            violations += 1
    assert violations == 0, (
        f"{weather}: {violations} moves exceeded max_speed={expected_max}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# UT-02  Snowy brake_limit: deceleration never exceeds 1 per axis
# ═══════════════════════════════════════════════════════════════════════════════

def test_snowy_brake_limit_x_axis():
    """UT-02a: Snowy car moving right (vx=3) cannot decelerate more than 1."""
    engine, _ = _oval_engine("Snowy")
    state     = CarState(4, 1, 3, 0)   # moving right at speed 3
    moves     = engine.get_legal_moves(state)
    for m in moves:
        ax = m.vx - state.vx
        if ax < 0:   # deceleration (opposes vx>0)
            assert ax >= -1, (
                f"Snowy brake violation: ax={ax} (limit=-1) at state {state}"
            )


def test_snowy_brake_limit_y_axis():
    """UT-02b: Snowy car moving down (vy=2) cannot decelerate more than 1."""
    engine, _ = _oval_engine("Snowy")
    state     = CarState(1, 3, 0, 2)   # moving down at speed 2
    moves     = engine.get_legal_moves(state)
    for m in moves:
        ay = m.vy - state.vy
        if ay < 0:
            assert ay >= -1, (
                f"Snowy brake violation: ay={ay} (limit=-1) at state {state}"
            )


def test_sunny_has_no_brake_restriction():
    """UT-02c: Sunny allows full deceleration (-2 per axis)."""
    engine, _ = _oval_engine("Sunny")
    state     = CarState(4, 1, 4, 0)
    axs       = [m.vx - state.vx for m in engine.get_legal_moves(state)]
    assert min(axs) <= -2, "Sunny should allow deceleration of -2"


# ═══════════════════════════════════════════════════════════════════════════════
# UT-03  Ordered A* path contains no finish tile before all CPs cleared
# ═══════════════════════════════════════════════════════════════════════════════

def test_ordered_path_no_early_finish():
    """UT-03: The path must not visit a finish tile before cp_idx reaches num_cps."""
    solver, engine, grid = _oval_solver()
    start                = CarState(2, 1, 0, 0)
    checkpoint_clusters  = [[(4, 1), (4, 2)]]
    finish_coords        = [(7, 1)]

    path, _ = solver.astar_search_ordered(
        start, checkpoint_clusters, finish_coords)

    assert path is not None, "No path found on oval track"

    finish_set   = set(finish_coords)
    cp_cleared   = False
    for state in path:
        if (state.x, state.y) in {(4,1),(4,2)}:
            cp_cleared = True
        if (state.x, state.y) in finish_set:
            assert cp_cleared, (
                f"Finish reached at ({state.x},{state.y}) before checkpoint cleared"
            )
            break   # finish can only appear once; after CPs cleared is fine


# ═══════════════════════════════════════════════════════════════════════════════
# UT-04  Ordered A* clears checkpoints in strict index order
# ═══════════════════════════════════════════════════════════════════════════════

def _make_two_cp_grid():
    """10×6 corridor with two sequential checkpoint bands."""
    rows, cols = 6, 12
    g = [[0]*cols for _ in range(rows)]
    # Straight top road
    for c in range(1, 11):
        g[1][c] = 1
    g[1][1]  = 2    # start
    g[1][10] = 3    # finish
    g[1][4]  = 4    # CP-0
    g[1][7]  = 5    # CP-1
    # Bottom road (reverse direction shortcut — should NOT be taken)
    for c in range(1, 11):
        g[4][c] = 1
    # Side connections
    for r in range(1, 5):
        g[r][1]  = 1
        g[r][10] = 1
    return g


def test_ordered_path_checkpoints_in_sequence():
    """UT-04: CP-0 (col 4) must appear in path before CP-1 (col 7)."""
    grid    = _make_two_cp_grid()
    engine  = PhysicsEngine(grid)
    solver  = AStarSolver(engine)
    start   = CarState(1, 1, 0, 0)
    cp0     = [(4, 1)]
    cp1     = [(7, 1)]
    finish  = [(10, 1)]

    path, _ = solver.astar_search_ordered(start, [cp0, cp1], finish)
    assert path is not None, "No path found"

    cp0_turn = next((i for i, s in enumerate(path) if (s.x, s.y) == (4,1)), None)
    cp1_turn = next((i for i, s in enumerate(path) if (s.x, s.y) == (7,1)), None)

    assert cp0_turn is not None, "CP-0 never reached"
    assert cp1_turn is not None, "CP-1 never reached"
    assert cp0_turn < cp1_turn, (
        f"CP-0 at turn {cp0_turn} should precede CP-1 at turn {cp1_turn}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# UT-05  Heuristic never overestimates true turns-to-goal (admissibility)
# ═══════════════════════════════════════════════════════════════════════════════

def test_heuristic_never_overestimates():
    """
    UT-05: For 50 CarStates on the oval, assert h(n) <= true_cost_to_goal.
    True cost is measured by running A* from each state to the finish
    and counting path length - 1 (turns).
    """
    solver, engine, grid = _oval_solver()
    finish_coords        = [(7, 1)]
    solver.set_goals_from_list(finish_coords)
    road_tiles = [(c, r)
                  for r in range(len(grid))
                  for c in range(len(grid[0]))
                  if grid[r][c] >= 1]

    violations = 0
    for (cx, cy) in road_tiles[:50]:     # sample first 50 road tiles
        test_state = CarState(cx, cy, 0, 0)
        h_val      = solver.heuristic(test_state)
        path, _    = solver.astar_search(test_state, finish_coords)
        if path is None:
            continue   # unreachable from this orientation — skip
        true_cost  = len(path) - 1
        if h_val > true_cost + 1e-9:
            violations += 1

    assert violations == 0, (
        f"Admissibility violated: {violations} states where h(n) > true_cost"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# UT-06  A* path length <= BFS path length on the same track
# ═══════════════════════════════════════════════════════════════════════════════

def test_astar_path_not_longer_than_bfs():
    """UT-06: A* with an admissible heuristic must produce an optimal (shortest) path."""
    solver, _, _ = _oval_solver()
    start        = CarState(2, 1, 0, 0)
    cp_clusters  = [[(4, 1), (4, 2)]]
    finish       = [(7, 1)]

    astar_path, _ = solver.astar_search_ordered(start, cp_clusters, finish)
    bfs_path, _   = solver._solve_pipeline(start, cp_clusters, finish, use_bfs=True)

    assert astar_path is not None and bfs_path, "One of the solvers failed"
    assert len(astar_path) <= len(bfs_path), (
        f"A* ({len(astar_path)} steps) longer than BFS ({len(bfs_path)} steps) — "
        "admissibility may be violated"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# UT-07  GA mutation preserves waypoint count
# ═══════════════════════════════════════════════════════════════════════════════

def test_ga_mutation_preserves_waypoint_count():
    """UT-07: mutate() must not change the number of waypoints."""
    import settings as s
    ga     = GeneticAlgorithm(population_size=2, generations=1, mutation_rate=1.0)
    chrome = Chromosome(ga.cols, ga.rows, num_waypoints=6)
    chrome.random_waypoints()
    original_count = len(chrome.waypoints)

    for _ in range(20):
        ga.mutate(chrome)
        assert len(chrome.waypoints) == original_count, (
            f"Waypoint count changed: {len(chrome.waypoints)} != {original_count}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# UT-08  GA grid has exactly one start tile after build
# ═══════════════════════════════════════════════════════════════════════════════

def test_ga_grid_has_exactly_one_start():
    """UT-08: Every built chromosome must contain exactly one start tile (value 2)."""
    import settings as s
    ga      = GeneticAlgorithm(population_size=5, generations=1, mutation_rate=0.3)
    ga.init_population()
    for i, chrome in enumerate(ga.population):
        start_count = sum(
            1 for row in chrome.grid for val in row if val == 2
        )
        assert start_count == 1, (
            f"Chromosome {i} has {start_count} start tiles (expected 1)"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# UT-09  Obstacle placement lands only on plain road tiles
# ═══════════════════════════════════════════════════════════════════════════════

def test_obstacles_only_on_road_tiles():
    """UT-09: generate_obstacles must not place obstacles on special tiles."""
    grid      = _make_oval_grid()
    obstacles = generate_obstacles(grid, n=20)
    for obs in obstacles:
        tile = grid[obs.y][obs.x]
        assert tile == 1, (
            f"Obstacle at ({obs.x},{obs.y}) on non-road tile (value={tile})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# UT-10  GameStateManager rejects all invalid transitions silently
# ═══════════════════════════════════════════════════════════════════════════════

def test_gsm_rejects_invalid_transitions():
    """UT-10: transition() must return False and leave state unchanged for illegal jumps."""
    invalid_pairs = [
        (GameState.BOOT_MENU, GameState.RUNNING),
        (GameState.RUNNING,   GameState.LOADING),
        (GameState.AI_PREVIEW, GameState.BOOT_MENU),
        (GameState.PRE_RACE,  GameState.WIN),
        (GameState.LOADING,   GameState.RUNNING),
    ]
    for src, dst in invalid_pairs:
        gsm    = GameStateManager(initial=src)
        result = gsm.transition(dst)
        assert result is False, (
            f"Expected False for {src} -> {dst}, got {result}"
        )
        assert gsm.state == src, (
            f"State corrupted: expected {src}, got {gsm.state} after illegal {src}->{dst}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])