[README.md](https://github.com/user-attachments/files/27102822/README.md)
# 🏁 Racetrack AI — A Kinematic Pathfinding Simulation

> A turn-based racing simulation where procedurally generated circuits meet rigorous AI navigation research. Built as a final-year Computer Science dissertation project, this system benchmarks **A\*** against **Uniform Cost Search** across infinitely unique, algorithmically evolved track topologies — all playable in real time.

---

## 📸 Track Previews

| Oval Circuit | Figure-8 | Box Circuit |
|:---:|:---:|:---:|
| *(Simple, wide)* | *(Self-overlapping)* | *(Tight corridors)* |

*All tracks are procedurally generated via a Genetic Algorithm + Catmull-Rom spline pipeline — no two runs are identical.*

---

##  Key Features

### Procedural Track Generation
- **Genetic Algorithm (GA)** evolves closed-circuit racing layouts over 35 generations across a population of 20 chromosomes
- Waypoints are interpolated using **Catmull-Rom splines** (`_build_grid` in `ga.py`) to produce smooth, organic curvature with C¹ tangent continuity
- A **curvature scoring system** (`_curvature_score`) uses inner products of unit tangent vectors to place checkpoints exclusively on straight sections, avoiding hairpin ambiguity
- **Sequential tile encoding** embeds circuit flow directly into the grid integer matrix (`4, 5, 6...` for ordered checkpoints, `3` for finish), making topological order immune to spatial proximity bugs
- Tracks are serialisable to **JSON** and reloadable via the in-game map selector
- Three **sharpness presets** (Gentle / Normal / Sharp) control `carve_radius`, `jitter`, and `mut_variance` per generation

### A\* AI Pathfinding
- The AI Hard agent navigates via a **5-dimensional sequentially constrained state space**: `(x, y, vx, vy, cp_idx)`
- Heuristic: **Chebyshev distance scaled by `max_speed`** — `h(n) = max(|dx|, |dy|) / V_max` — proven admissible because the physics engine applies acceleration independently per axis
- A `(1 + 1e-4)` tie-breaking multiplier provides a near-optimal **(1+ε)-admissible** heuristic that reduces node expansion with negligible optimality cost
- **Dynamic spatial masking** (`avoid_tile=3`) blinds the solver to the finish line until all sequential checkpoints are cleared, enforcing circuit flow without modifying core A\* logic
- **Lazy deletion** via a `g_score` dictionary eliminates stale priority queue entries in O(1), avoiding the overhead of a decrease-key operation
- The **Uniform Cost Search (BFS) baseline** shares the same state space and is used for pre-race empirical comparison of nodes explored and solve time
- The A\* mega-path is **pre-computed offline** before the race starts and stored in `Racer.precomputed_path` for zero-latency playback during the race

### Dynamic Weather Physics
- Three hot-swappable weather modes modify the **Markov transition model** at runtime via `PhysicsEngine.set_weather()`:
  - **Sunny** — full acceleration (±2), max speed 5, free braking
  - **Rainy** — reduced grip (±1 accel, max speed 3), branching factor drops from 25 to 9
  - **Snowy** — normal acceleration but asymmetric braking: a **dot-product directional filter** (`ax * vx < 0`) caps opposing acceleration at 1, simulating wheel-spin and forcing the solver to plan deceleration sequences earlier
- Weather changes alter the solver's **computational complexity class** while the Chebyshev heuristic remains strictly admissible across all modes (divisor scales dynamically with `V_max`)

### Physics Engine & Collision Detection
- Fully discrete integer-grid physics: velocity vectors `(vx, vy)` are bounded by `[-V_max, V_max]`
- **Continuous Collision Detection (CCD)** via **Bresenham's Line Algorithm** (`_check_path` in `game_engine.py`) samples every intermediate grid cell along a transition vector, preventing high-velocity tunnelling through 1-tile-wide walls
- A separate `get_crossed_tiles()` method uses Bresenham to detect checkpoint and finish line crossings mid-move, ensuring they are never missed at high speed

### Multi-Agent Turn-Based Racing
- Four simultaneous racers: **Player**, **CPU Easy** (random momentum-biased), **CPU Medium** (greedy Manhattan-distance minimisation), **CPU Hard** (optimal A\* pre-computed path)
- Lives system, crash respawn to last cleared checkpoint, wrong-way detection via velocity-forward-vector dot product
- **Ghost car** system: records the player's optimal run per track (keyed by MD5 hash of the grid), replays it as a semi-transparent overlay, and maintains a 5-entry leaderboard per track

### Algorithmic Transparency HUD
- Real-time **AI Visibility HUD** displays: path length, nodes explored, and solve time for the CPU Hard agent
- **AI Preview state** animates the A\* exploration tree before the race starts
- Developer Mode (T key) toggles the side-by-side A\* vs BFS performance comparison panel

### Procedural Hazards
- **Potholes** (one-shot, costs a life) and **Oil Spills** (persistent, randomises acceleration for 3 turns) placed on valid road tiles only
- A `_footprint_safe` 3×3 grid scan prevents hazards from blocking checkpoints or finish lines

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| Rendering & Input | [Pygame](https://www.pygame.org/) |
| Priority Queue | `heapq` (Python standard library) |
| Serialisation | `json` (Python standard library) |
| Ghost file integrity | `hashlib` (MD5 track ID), `os.replace()` atomic writes |
| Maths | `math` (Catmull-Rom, dot products, `math.hypot`) |
| Randomness | `random` (GA mutation, waypoint jitter, obstacle placement) |

> **No third-party AI or pathfinding libraries are used.** A\*, BFS, the physics engine, the Genetic Algorithm, and all spline mathematics are implemented from scratch.

---

## ⚙️ Installation & Setup

### Prerequisites
- Python **3.11 or higher** (uses `int | None` union type hints)
- `pip`

### 1. Clone the repository
```bash
git clone https://github.com/your-username/racetrack-ai.git
cd racetrack-ai
```

### 2. Create and activate a virtual environment
```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install pygame
```

> The project has a single external dependency. All other modules (`heapq`, `json`, `math`, `random`, `hashlib`, `os`, `time`) are Python standard library.

### 4. Run the game
```bash
python main.py
```

---

## Project Structure

```
racetrack-ai/
│
├── main.py               # Entry point — game loop, state orchestration, rendering
├── game_state_manager.py # Validated finite state machine (DAG of legal transitions)
├── game_engine.py        # Discrete physics — get_legal_moves(), Bresenham CCD
├── solver.py             # A*, BFS, 5D ordered solver, cluster extraction
├── ga.py                 # Genetic Algorithm — Chromosome, Catmull-Rom, fitness oracle
├── car.py                # CarState (immutable value object), Racer (mutable entity)
├── track.py              # Track loading (PNG + JSON), grid-to-surface rendering
├── ui.py                 # UIRenderer — HUD, menus, leaderboard, AI preview
├── obstacles.py          # Pothole / OilSpill placement with footprint safety check
├── ghost_recorder.py     # Ghost recording, JSON persistence, GhostCar replay
├── settings.py           # Single source of truth — physics, colours, GA presets
│
├── custom_track_*.json   # Saved procedurally generated track layouts
├── ghosts/               # Per-track ghost run files (auto-created)
└── track*.png            # Hand-authored fallback tracks (legacy PNG format)
```

---

## Technical Deep Dive

### Procedural Track Generation: SB-PCG via Genetic Algorithm

Track generation is implemented as **Search-Based Procedural Content Generation (SB-PCG)**, where the A\* solver itself acts as the fitness oracle.

**Genome representation:** Each `Chromosome` stores `N` waypoints placed roughly on a circle with randomised jitter. The genome is a fixed-length list of `(x, y)` tuples.

**Grid construction:** Waypoints are connected using the **Catmull-Rom spline** formula:

```
P(t) = 0.5 * [t³  t²  t  1] · M_CR · [P_{k-1}  P_k  P_{k+1}  P_{k+2}]ᵀ
```

where `M_CR` is the standard Catmull-Rom basis matrix. This guarantees C¹ tangent continuity — the velocity vector never experiences a physically impossible discontinuity at waypoint junctions. A circular brush (`_carve_circle`) then stamps a corridor of configurable `radius` along each sampled point on the spline.

**Fitness function:** A track's fitness is evaluated by running A\* from start to finish and scoring:

```python
fitness = (path_length * 10) + (direction_changes * 1.25) + (road_tiles * 0.3)
```

Unsolvable tracks receive a fitness of `0` and are eliminated from the gene pool. This guarantees **100% start-to-finish path existence** in the output population.

**Evolutionary operators:**
- **Selection:** Tournament selection (k=3)
- **Crossover:** Uniform crossover — each waypoint is independently inherited from either parent, preserving local track "building blocks" as described by Holland's Schema Theorem
- **Mutation:** Random jitter applied per waypoint at rate `μ = 0.3`; shift range is controlled by the sharpness preset
- **Elitism:** The single highest-fitness chromosome passes to the next generation unmodified, guaranteeing monotonically non-decreasing best fitness

**Checkpoint placement:** After grid construction, checkpoint lines are drawn perpendicular to the track flow at waypoints selected by ascending curvature score, ensuring they land on the flattest, most readable sections of the circuit.

---

### A\* Pathfinding: 5D Sequentially Constrained Search

The core algorithmic challenge is that a standard 2D shortest-path search cannot navigate a closed circuit — it will always cut directly to the finish line. This project solves it with a 5D state representation:

```
S = (x, y, vx, vy, cp_idx)
```

The fifth dimension `cp_idx` tracks how many sequential checkpoints have been cleared. Two states at the same `(x, y, vx, vy)` with different `cp_idx` values are treated as **entirely distinct nodes**, forcing the solver to complete the circuit in order.

**Admissible heuristic:**

```
h(n) = max(|x_n − x_goal|, |y_n − y_goal|) / V_max
```

This Chebyshev distance divided by `V_max` is admissible because the physics engine applies acceleration independently per axis — a diagonal displacement `(d, d)` can be closed in `d / V_max` turns, exactly matching the heuristic value. Manhattan distance would overestimate diagonal cases by a factor of 2.

**Dynamic spatial masking:** Rather than modifying the heuristic for circuit enforcement, the finish tile (`value=3`) is treated as a lethal wall during phases where `cp_idx < num_checkpoints`. This is implemented via the `avoid_tile` parameter and costs zero additional overhead.

**Lazy deletion:** The open set uses a standard `heapq` with no decrease-key operation. When a cheaper path to a node is found, a new entry is pushed. Stale (higher-cost) entries are discarded in O(1) when popped:

```python
if g > g_score.get(cur, INF):
    continue  # stale entry — skip
```

---

### Physics Engine: Discrete Kinematic Model

The simulation uses an integer-grid Markov Decision Process. At each turn, the agent selects an acceleration `(ax, ay) ∈ [-accel_limit, accel_limit]²`, which updates velocity:

```
vx' = clamp(vx + ax, -V_max, V_max)
vy' = clamp(vy + ay, -V_max, V_max)
```

The new position is `(x + vx', y + vy')`.

**Continuous Collision Detection** prevents tunnelling. Rather than checking only the destination tile, `_check_path` uses Bresenham's line to sample every intermediate cell:

```python
for i in range(1, steps + 1):
    t  = i / steps
    xt = int(x1 + t * (x2 - x1))
    yt = int(y1 + t * (y2 - y1))
    if not self._is_safe(xt, yt):
        return False
```

At `V_max = 5`, a car traverses up to 5 tiles per turn — without CCD, a 1-tile wall is invisible to endpoint-only checks.

**Snowy weather — dot-product braking filter:**

```python
if ax * current_state.vx < 0 and abs(ax) > self.brake_limit:
    continue  # reject this acceleration choice
```

The condition `ax * vx < 0` is true exactly when the chosen acceleration opposes the current velocity (i.e. braking). Capping this at `brake_limit = 1` asymmetrically restricts deceleration while leaving forward acceleration unconstrained, accurately modelling wheel-spin on a low-traction surface.

---

## Controls

### In-Race

| Key | Action |
|---|---|
| `↑` `↓` `←` `→` | Select acceleration delta (+2, -2, +1, -1 per axis) |
| `Space` | Confirm acceleration and end turn |
| `Esc` | Pause race |

### Menus & Navigation

| Key / Action | Screen | Effect |
|---|---|---|
| `N` | Boot Menu | Generate a new track via Genetic Algorithm |
| `M` | Boot Menu | Open saved track selector |
| `S` | Pre-Race (READY) | Save current generated track to JSON |
| `T` | Pre-Race (READY) | Toggle Developer Mode (A\* vs BFS stats) |
| `R` | Win / Lose screen | Instant restart (cached — skips A\* re-solve) |
| `Space` | Pre-Race (READY) | Begin race |
| `Space` | Win / Lose screen | Return to menu |

### GA Setup Screen

| Control | Options |
|---|---|
| Waypoint count | 4 – 10 (slider) |
| Sharpness preset | Gentle / Normal / Sharp |
| Weather | Sunny / Rainy / Snowy |

---

## Testing

Unit tests are located in `test_solver.py` and cover:

| Test ID | Description |
|---|---|
| UT-01 | Legal successors never exceed weather-defined `max_speed` |
| UT-02 | Snowy braking limit correctly restricts opposing acceleration |
| UT-03 | Ordered A\* cannot reach the finish tile before all checkpoints are cleared |
| UT-04 | Solver navigates sequential checkpoint clusters in correct numerical order |
| UT-05 | Heuristic `h(n)` never overestimates true turn cost (admissibility certificate) |
| UT-06 | A\* path length ≤ BFS path length for all test cases |
| UT-07 | GA crossover and mutation preserve fixed waypoint count |
| UT-08 | Every generated chromosome contains exactly one start tile |
| UT-09 | Procedural hazards spawn only on plain road tiles (value == 1) |
| UT-10 | `GameStateManager` silently rejects all invalid state transitions |

Run tests with:
```bash
python -m pytest test_solver.py -v
```

---

## Experimental Results (Summary)

| Research Question | Finding |
|---|---|
| **RQ1 — Admissibility** | A\* produced paths of identical length to BFS in 100% of N=20 generated tracks |
| **RQ2 — Overhead vs Complexity** | Pearson r = 0.74 positive correlation between GA fitness score and A\* node expansion count |
| **RQ3 — Weather Robustness** | Rainy conditions reduced mean nodes explored (branching factor 25→9); Snowy conditions increased node expansion by requiring deep deceleration planning |

---

## Potential Extensions

- **Multi-lap kinematic continuity** — pipe terminal state `(x, y, vx, vy)` of lap N as initial state of lap N+1 to eliminate resetting behaviour
- **Full circuit fitness oracle** — replace point-to-point A\* solvability check in `calculate_fitness` with the full 5D ordered solver (at the cost of generation time)
- **Imitation learning** — use `Racer.precomputed_path` as labelled training data for a supervised neural network agent
- **Mixed-initiative track editor** — allow human waypoint sculpting post-GA to create a Human-in-the-Loop PCG pipeline
- **Variable-length genome** — allow GA mutation to insert or delete waypoints, removing the hyperparameter ceiling imposed by fixed `num_waypoints`

---

## Licence

This project was developed as a final-year undergraduate dissertation at the **School of Computing and Mathematical Sciences, University of Leicester** (CO3201).

---

*Built with Python · Pygame · ClaudeAi · A\* · Genetic Algorithms · Catmull-Rom Splines*
