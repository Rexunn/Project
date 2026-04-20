"""
evaluation/run_experiments.py
------------------------------
Generates all quantitative data for Chapter 6 Experiments 1-3.

Outputs (written to evaluation/results/):
  exp1_admissibility.csv      — Exp 1 raw data
  exp2_complexity.csv         — Exp 2 raw data
  exp3_weather.csv            — Exp 3 raw data
  fig_6_1_admissibility.png   — Scatter: A* vs BFS path length
  fig_6_2_complexity.png      — Scatter + regression: fitness vs nodes
  fig_6_3_quartile_bars.png   — Bar: A*/BFS nodes by complexity quartile
  fig_6_4_weather_bars.png    — Grouped bar: nodes per weather mode
  fig_6_5_weather_box.png     — Box plot: path length per weather mode

Dependencies:
  pip install matplotlib numpy scipy
"""

import os, sys, csv, json, time, math
from pathlib import Path

# ── Headless Pygame ──────────────────────────────────────────────────────────
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pygame
pygame.init()

import matplotlib
matplotlib.use("Agg")   # non-interactive backend — no window needed
import matplotlib.pyplot as plt
import numpy as np

import settings as s
from car import CarState
from game_engine import PhysicsEngine
from solver import AStarSolver
from track import Track
from ga import GeneticAlgorithm, Chromosome

RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Helper utilities
# ═══════════════════════════════════════════════════════════════════════════════

def find_start(grid):
    for r, row in enumerate(grid):
        for c, val in enumerate(row):
            if val == 2:
                return CarState(c, r, 0, 0)
    return CarState(5, 5, 0, 0)


def extract_checkpoints(solver, grid):
    """Reproduce setup_race checkpoint extraction logic."""
    checkpoint_clusters = []
    cp_val = 4
    while True:
        clusters = solver._get_clusters(cp_val)
        if not clusters:
            break
        if cp_val == 4 and len(clusters) > 1:
            # Use geometric sort for consistency
            cx_grid = len(grid[0]) // 2
            cy_grid = len(grid) // 2
            def ang(cl):
                ax = sum(x for x,_ in cl)/len(cl)
                ay = sum(y for _,y in cl)/len(cl)
                return math.atan2(ay-cy_grid, ax-cx_grid)
            checkpoint_clusters = sorted(clusters, key=ang)
            break
        else:
            checkpoint_clusters.extend(clusters)
        cp_val += 1
    return checkpoint_clusters


def run_both_solvers(grid, weather="Sunny"):
    """Run A* (ordered) and BFS (pipeline) on a grid. Return metrics dict."""
    engine = PhysicsEngine(grid, weather=weather)
    solver = AStarSolver(engine)
    start  = find_start(grid)
    cps    = extract_checkpoints(solver, grid)

    if not cps:
        return None

    astar_path, astar_exp, astar_time = solver.solve(
        start, cps, use_bfs=False)
    bfs_path,   bfs_exp,   bfs_time   = solver.solve(
        start, cps, use_bfs=True)

    if not astar_path or not bfs_path:
        return None

    return {
        "astar_path_len":   len(astar_path),
        "astar_nodes":      len(astar_exp),
        "astar_time_ms":    round(astar_time * 1000, 2),
        "bfs_path_len":     len(bfs_path),
        "bfs_nodes":        len(bfs_exp),
        "bfs_time_ms":      round(bfs_time * 1000, 2),
        "node_ratio":       round(len(astar_exp) / max(1, len(bfs_exp)), 4),
        "weather":          weather,
        "num_cps":          len(cps),
    }


def calculate_fitness(grid):
    """Proxy fitness: A*-path-length × 10 + direction_changes × 1.25."""
    engine = PhysicsEngine(grid)
    solver = AStarSolver(engine)
    start  = find_start(grid)
    cps    = extract_checkpoints(solver, grid)
    if not cps:
        return 0
    finish = [(x,y) for y in range(len(grid))
                    for x in range(len(grid[0]))
                    if grid[y][x] == 3]
    path, _ = solver.astar_search(start, finish)
    if not path:
        return 0
    dc = sum(1 for i in range(1,len(path))
             if path[i-1].vx != path[i].vx or path[i-1].vy != path[i].vy)
    road = sum(1 for row in grid for v in row if v >= 1)
    return len(path)*10 + dc*1.25 + road*0.3


# ═══════════════════════════════════════════════════════════════════════════════
# Load saved JSON tracks
# ═══════════════════════════════════════════════════════════════════════════════

def load_json_tracks():
    tracks = []
    for p in sorted(PROJECT_ROOT.glob("*.json")):
        try:
            with open(p) as f:
                grid = json.load(f)
            tracks.append((p.name, grid))
            print(f"  Loaded: {p.name}")
        except Exception as e:
            print(f"  Skipped {p.name}: {e}")
    return tracks


# ═══════════════════════════════════════════════════════════════════════════════
# Generate GA tracks
# ═══════════════════════════════════════════════════════════════════════════════

def generate_tracks(n=12, num_waypoints=6, sharpness="Normal"):
    """Generate n tracks using the GA. Progress printed to console."""
    import settings as s
    preset = s.GA_SHARPNESS_PRESETS.get(sharpness, s.GA_SHARPNESS_PRESETS["Normal"])
    tracks = []
    print(f"  Generating {n} tracks (waypoints={num_waypoints}, sharpness={sharpness})...")
    for i in range(n):
        ga   = GeneticAlgorithm(
            population_size=10, generations=20, mutation_rate=0.3,
            num_waypoints=num_waypoints, sharpness=sharpness)
        best = ga.run(update_callback=None)
        if best.fitness > 0:
            tracks.append((f"ga_{sharpness}_{i}", best.grid))
            print(f"    Track {i+1}/{n} — fitness={best.fitness:.0f}")
        else:
            print(f"    Track {i+1}/{n} — FAILED (fitness=0), skipping")
    return tracks


# ═══════════════════════════════════════════════════════════════════════════════
# Experiment 1 — RQ1: A* Admissibility
# ═══════════════════════════════════════════════════════════════════════════════

def experiment_1(tracks):
    """
    Hypothesis: A* path length <= BFS path length on every track (0 violations).
    Runs both solvers on all tracks and records path lengths.
    """
    print("\n=== EXPERIMENT 1: A* ADMISSIBILITY ===")
    rows = []
    violations = 0

    for name, grid in tracks:
        result = run_both_solvers(grid)
        if result is None:
            print(f"  {name}: SKIP (unsolvable)")
            continue
        result["track"] = name
        rows.append(result)
        ok = result["astar_path_len"] <= result["bfs_path_len"]
        if not ok:
            violations += 1
        print(f"  {name}: A*={result['astar_path_len']} BFS={result['bfs_path_len']} "
              f"{'OK' if ok else '!!! VIOLATION'}")

    print(f"\nAdmissibility violations: {violations} / {len(rows)}")

    # Save CSV
    csv_path = RESULTS_DIR / "exp1_admissibility.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)
    print(f"Saved: {csv_path}")

    # Figure 6.1 — Scatter: A* vs BFS path length
    astar_lens = [r["astar_path_len"] for r in rows]
    bfs_lens   = [r["bfs_path_len"]   for r in rows]
    fig, ax = plt.subplots(figsize=(6,5))
    ax.scatter(bfs_lens, astar_lens, color="#185FA5", alpha=0.8, zorder=3)
    lim = max(max(bfs_lens), max(astar_lens)) * 1.05
    ax.plot([0,lim],[0,lim], color="#888", linestyle="--", linewidth=1,
            label="y = x (equal length)")
    ax.set_xlabel("BFS path length (steps)")
    ax.set_ylabel("A* path length (steps)")
    ax.set_title("Fig 6.1 — A* vs BFS path length across all tracks")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "fig_6_1_admissibility.png", dpi=150)
    plt.close(fig)
    print(f"Saved: fig_6_1_admissibility.png")

    return rows


# ═══════════════════════════════════════════════════════════════════════════════
# Experiment 2 — RQ2: Track Complexity vs Solver Overhead
# ═══════════════════════════════════════════════════════════════════════════════

def experiment_2(tracks):
    """
    Hypothesis: Positive correlation between GA fitness and A* nodes explored.
    """
    print("\n=== EXPERIMENT 2: COMPLEXITY vs SOLVER OVERHEAD ===")
    rows = []

    for name, grid in tracks:
        fitness = calculate_fitness(grid)
        if fitness == 0:
            print(f"  {name}: fitness=0, skipping")
            continue
        result = run_both_solvers(grid)
        if result is None:
            continue
        result["track"]   = name
        result["fitness"] = round(fitness, 1)
        rows.append(result)
        print(f"  {name}: fitness={fitness:.0f}  A*_nodes={result['astar_nodes']}")

    if len(rows) < 3:
        print("  Not enough data for Exp 2 (need ≥3 solvable tracks)")
        return rows

    csv_path = RESULTS_DIR / "exp2_complexity.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)
    print(f"Saved: {csv_path}")

    fitness  = np.array([r["fitness"]    for r in rows])
    nodes    = np.array([r["astar_nodes"] for r in rows])
    ratio    = np.array([r["node_ratio"]  for r in rows])

    # Pearson r
    if len(fitness) >= 3:
        r_val = np.corrcoef(fitness, nodes)[0,1]
        print(f"  Pearson r (fitness vs A* nodes): {r_val:.3f}")
    else:
        r_val = float("nan")

    # Figure 6.2 — Scatter + regression
    fig, ax = plt.subplots(figsize=(6,5))
    ax.scatter(fitness, nodes, color="#185FA5", alpha=0.8, zorder=3)
    if len(fitness) >= 2:
        m, b  = np.polyfit(fitness, nodes, 1)
        xs    = np.linspace(fitness.min(), fitness.max(), 100)
        ax.plot(xs, m*xs + b, color="#993C1D", linewidth=1.5,
                label=f"r = {r_val:.2f}")
    ax.set_xlabel("GA fitness score")
    ax.set_ylabel("A* nodes explored")
    ax.set_title("Fig 6.2 — Track complexity vs A* exploration overhead")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "fig_6_2_complexity.png", dpi=150)
    plt.close(fig)

    # Figure 6.3 — Bar by complexity quartile
    if len(rows) >= 4:
        qs    = np.percentile(fitness, [25, 50, 75])
        labels = ["Low", "Medium", "High", "Very High"]
        groups = {l: {"astar":[], "bfs":[]} for l in labels}
        for r in rows:
            f = r["fitness"]
            if   f <= qs[0]: g = "Low"
            elif f <= qs[1]: g = "Medium"
            elif f <= qs[2]: g = "High"
            else:            g = "Very High"
            groups[g]["astar"].append(r["astar_nodes"])
            groups[g]["bfs"].append(r["bfs_nodes"])

        x     = np.arange(len(labels))
        w_bar = 0.35
        means_a = [np.mean(groups[l]["astar"]) if groups[l]["astar"] else 0 for l in labels]
        means_b = [np.mean(groups[l]["bfs"])   if groups[l]["bfs"]   else 0 for l in labels]
        fig, ax = plt.subplots(figsize=(7,5))
        ax.bar(x - w_bar/2, means_a, w_bar, label="A*",  color="#185FA5", alpha=0.85)
        ax.bar(x + w_bar/2, means_b, w_bar, label="BFS", color="#993C1D", alpha=0.85)
        ax.set_xticks(x); ax.set_xticklabels(labels)
        ax.set_xlabel("Track complexity quartile")
        ax.set_ylabel("Mean nodes explored")
        ax.set_title("Fig 6.3 — A* vs BFS exploration by track complexity")
        ax.legend()
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(RESULTS_DIR / "fig_6_3_quartile_bars.png", dpi=150)
        plt.close(fig)
        print(f"Saved: fig_6_3_quartile_bars.png")

    return rows


# ═══════════════════════════════════════════════════════════════════════════════
# Experiment 3 — RQ3: Weather Mode Impact
# ═══════════════════════════════════════════════════════════════════════════════

def experiment_3(tracks, n_tracks=5):
    """
    Hypothesis: Rainy reduces nodes explored; Snowy increases path length.
    Runs A* on the same n_tracks under Sunny, Rainy, and Snowy.
    """
    print("\n=== EXPERIMENT 3: WEATHER IMPACT ===")
    MODES    = ["Sunny", "Rainy", "Snowy"]
    rows     = []
    # Use the first n_tracks solvable tracks
    test_tracks = [(n,g) for n,g in tracks
                   if run_both_solvers(g) is not None][:n_tracks]

    if not test_tracks:
        print("  No solvable tracks available for Exp 3.")
        return []

    for name, grid in test_tracks:
        for weather in MODES:
            result = run_both_solvers(grid, weather=weather)
            if result is None:
                continue
            result["track"] = name
            rows.append(result)
            print(f"  {name} [{weather}]: "
                  f"A*_nodes={result['astar_nodes']}  "
                  f"A*_len={result['astar_path_len']}")

    csv_path = RESULTS_DIR / "exp3_weather.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)
    print(f"Saved: {csv_path}")

    # Figure 6.4 — Grouped bar: nodes explored per weather mode
    by_mode   = {m: [r["astar_nodes"]    for r in rows if r["weather"]==m] for m in MODES}
    means_n   = [np.mean(by_mode[m]) if by_mode[m] else 0 for m in MODES]
    colours   = ["#639922", "#185FA5", "#9FE1CB"]
    fig, ax = plt.subplots(figsize=(6,5))
    ax.bar(MODES, means_n, color=colours, alpha=0.88)
    ax.set_xlabel("Weather mode")
    ax.set_ylabel("Mean A* nodes explored")
    ax.set_title("Fig 6.4 — A* nodes explored by weather mode")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "fig_6_4_weather_bars.png", dpi=150)
    plt.close(fig)

    # Figure 6.5 — Box plot: path length per weather mode
    by_mode_len = {m: [r["astar_path_len"] for r in rows if r["weather"]==m]
                   for m in MODES}
    data_box    = [by_mode_len[m] for m in MODES]
    fig, ax = plt.subplots(figsize=(6,5))
    bp = ax.boxplot(data_box, labels=MODES, patch_artist=True,
                    medianprops={"color":"white","linewidth":2})
    for patch, col in zip(bp["boxes"], colours):
        patch.set_facecolor(col)
        patch.set_alpha(0.82)
    ax.set_xlabel("Weather mode")
    ax.set_ylabel("A* path length (steps)")
    ax.set_title("Fig 6.5 — Path length distribution by weather mode")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "fig_6_5_weather_box.png", dpi=150)
    plt.close(fig)
    print("Saved: fig_6_4_weather_bars.png, fig_6_5_weather_box.png")

    # Print summary statistics
    print("\nWeather summary:")
    for m in MODES:
        ns = by_mode[m]
        ls = by_mode_len[m]
        if ns:
            print(f"  {m:6s}: mean_nodes={np.mean(ns):.0f}  "
                  f"mean_path={np.mean(ls):.1f}  "
                  f"std_path={np.std(ls):.1f}")

    return rows


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("CHAPTER 6 EVALUATION RUNNER")
    print("=" * 60)

    # ── Step 1: Load saved JSON tracks ───────────────────────────────────────
    print("\nLoading saved JSON tracks...")
    saved = load_json_tracks()
    print(f"  Found {len(saved)} saved tracks")

    # ── Step 2: Generate additional GA tracks ─────────────────────────────────
    # Adjust n to produce ~20 total tracks
    n_to_generate = max(0, 17 - len(saved))
    if n_to_generate > 0:
        print(f"\nGenerating {n_to_generate} GA tracks to reach ~20 total...")
        generated = generate_tracks(n=n_to_generate, num_waypoints=6,
                                    sharpness="Normal")
    else:
        generated = []

    all_tracks = saved + generated
    print(f"\nTotal tracks available: {len(all_tracks)}")

    if len(all_tracks) == 0:
        print("ERROR: No tracks available. Place .json track files in the project root.")
        sys.exit(1)

    # ── Run experiments ────────────────────────────────────────────────────────
    e1 = experiment_1(all_tracks)
    e2 = experiment_2(all_tracks)
    e3 = experiment_3(all_tracks, n_tracks=5)

    print("\n" + "="*60)
    print("ALL EXPERIMENTS COMPLETE")
    print(f"Results saved to: {RESULTS_DIR}")
    print("="*60)