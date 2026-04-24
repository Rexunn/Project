"""
solver.py
---------
A* and BFS solvers for the racetrack problem.

"""

from queue import PriorityQueue
from car import CarState
import time


# ═══════════════════════════════════════════════════════════════════════════════
# Augmented state for checkpoint-ordered pathfinding
# ═══════════════════════════════════════════════════════════════════════════════

class OrderedCarState:
    """
    (x, y, vx, vy, cp_idx) — extends CarState with the index of the
    next required checkpoint.

    cp_idx == 0               car must clear checkpoints[0] next
    cp_idx == len(clusters)   all checkpoints cleared; car must reach finish

    """
    __slots__ = ('x', 'y', 'vx', 'vy', 'cp_idx')

    def __init__(self, x: int, y: int, vx: int, vy: int, cp_idx: int = 0):
        self.x      = x
        self.y      = y
        self.vx     = vx
        self.vy     = vy
        self.cp_idx = cp_idx

    def __eq__(self, other) -> bool:
        return (self.x, self.y, self.vx, self.vy, self.cp_idx) == \
               (other.x, other.y, other.vx, other.vy, other.cp_idx)

    def __hash__(self) -> int:
        return hash((self.x, self.y, self.vx, self.vy, self.cp_idx))

    def __lt__(self, other) -> bool:
        return False  # tie-break deferred to the counter in the priority tuple

    def to_car_state(self) -> CarState:
        return CarState(self.x, self.y, self.vx, self.vy)

    @classmethod
    def from_car_state(cls, cs: CarState, cp_idx: int = 0) -> "OrderedCarState":
        return cls(cs.x, cs.y, cs.vx, cs.vy, cp_idx)


# ═══════════════════════════════════════════════════════════════════════════════
# Solver
# ═══════════════════════════════════════════════════════════════════════════════

class AStarSolver:

    def __init__(self, engine):
        self.engine = engine
        self.cols   = engine.cols
        self.rows   = engine.rows
        self.current_goals: list = []

    # ── Legacy helpers (used internally and for unit tests) ───────────────────

    def set_goals_from_list(self, coords_list: list) -> None:
        self.current_goals = coords_list

    def heuristic(self, state) -> float:
        """
        Chebyshev distance to nearest goal/max speed
        """
        if not self.current_goals:
            return 0.0
        max_speed = self.engine.max_speed
        return min(
            max(abs(state.x - gx), abs(state.y - gy))
            for gx, gy in self.current_goals
        ) / max_speed

    
    def astar_search(self, start_state, target_coords: list,
                     avoid_tile: int | None = None):
        """Optimised to single target set"""

        self.set_goals_from_list(target_coords)
        if not self.current_goals:
            return None, []

               goal_set   = frozenset((int(gx), int(gy)) for gx, gy in target_coords)
        max_speed  = self.engine.max_speed
        _track     = self.engine.track          # LOAD_FAST in inner loop
        _get_moves = self.engine.get_legal_moves
        _avoid     = avoid_tile
        _INF       = 10 ** 9
 
        # ── Bounding-box heuristic (O(1)) ────────────────────────────────────
        xs     = [gx for gx, _ in target_coords]
        ys     = [gy for _, gy in target_coords]
        bx_min = min(xs);  bx_max = max(xs)
        by_min = min(ys);  by_max = max(ys)
 
        def _h(x: int, y: int) -> float:
            """Chebyshev distance from (x,y) to nearest point in AABB / max_speed."""
            dx = max(0, bx_min - x, x - bx_max)
            dy = max(0, by_min - y, y - by_max)
            return max(dx, dy) / max_speed
 
        # ── Search init ───────────────────────────────────────────────────────
        # Key: (x, y, vx, vy) — plain tuple, C-level hash, no object overhead
        start_key = (start_state.x, start_state.y,
                     start_state.vx, start_state.vy)
        h0 = _h(start_state.x, start_state.y)
 
        # heap entry: (f, g, counter, key)
        # counter guarantees stable ordering when f and g are tied
        heap      = [(h0, 0, 0, start_key)]
        g_score   = {start_key: 0}
        came_from = {start_key: None}
        explored  = []          # list of raw tuple keys (converted at return)
        counter   = 1
 
        _heappush = heapq.heappush
        _heappop  = heapq.heappop
 
        while heap:
            f, g, _, cur = _heappop(heap)
 
            # ── Lazy deletion: skip stale entries in O(1) ──────────────────
            if g > g_score.get(cur, _INF):
                continue
 
            explored.append(cur)
            x, y, vx, vy = cur
 
            # ── Goal test ──────────────────────────────────────────────────
            if (x, y) in goal_set:
                # Reconstruct as list[CarState]
                path = []
                node = cur
                while node is not None:
                    path.append(CarState(node[0], node[1], node[2], node[3]))
                    node = came_from[node]
                path.reverse()
                expl = [CarState(s[0], s[1], s[2], s[3]) for s in explored]
                return path, expl
 
            # ── Expand ────────────────────────────────────────────────────
            proxy = CarState(x, y, vx, vy)
            for nxt in _get_moves(proxy):
                nx, ny   = nxt.x,  nxt.y
                nvx, nvy = nxt.vx, nxt.vy
                if _avoid is not None and _track[ny][nx] == _avoid:
                    continue
                nxt_key = (nx, ny, nvx, nvy)
                new_g   = g + 1
                if new_g < g_score.get(nxt_key, _INF):
                    g_score[nxt_key]   = new_g
                    came_from[nxt_key] = cur
                    _heappush(heap,
                               (new_g + _h(nx, ny), new_g, counter, nxt_key))
                    counter += 1
 
        expl = [CarState(s[0], s[1], s[2], s[3]) for s in explored]
        return None, expl

    def bfs_search(self, start_state, target_coords: list,
                   avoid_tile: int | None = None):
        """Uninformed BFS to a single target set. Used by BFS pipeline."""
        self.set_goals_from_list(target_coords)
        if not self.current_goals:
            return None, []

        pq          = PriorityQueue()
        pq.put((0, 0, start_state))
        came_from   = {start_state: None}
        cost_so_far = {start_state: 0}
        explored    = []

        while not pq.empty():
            _, _, current = pq.get()
            explored.append(current)
            if (current.x, current.y) in self.current_goals:
                return self._reconstruct_path(came_from, current), explored
            for nxt in self.engine.get_legal_moves(current):
                if avoid_tile is not None:
                    if self.engine.track[nxt.y][nxt.x] == avoid_tile:
                        continue
                new_cost = cost_so_far[current] + 1
                if nxt not in cost_so_far or new_cost < cost_so_far[nxt]:
                    cost_so_far[nxt] = new_cost
                    pq.put((new_cost, 0, nxt))
                    came_from[nxt] = current

        return None, explored

    # ── NEW: Checkpoint-ordered A* (the Step 2 fix) ───────────────────────────

    def _heuristic_ordered(self, state: OrderedCarState,
                            checkpoint_clusters: list,
                            finish_coords: list,
                            num_cps: int) -> float:
        """
        Admissible heuristic for the augmented state space.

        Points toward checkpoint_clusters[state.cp_idx] while checkpoints
        remain, then toward the nearest finish tile.

        Admissibility proof (augmented case)
        -------------------------------------
        Let h*(n) = true optimal turns from n to goal in the AUGMENTED space.
        The augmented space only adds checkpoint constraints — it cannot make
        any path shorter than the unconstrained minimum.  Therefore:

            h_ordered(n) = dist_to_next_target / 3.0
                         <= unconstrained_h*(n)
                         <= augmented_h*(n)

        Admissibility is preserved by transitivity.
        """
        if state.cp_idx < num_cps:
            cluster = checkpoint_clusters[state.cp_idx]
            return min(abs(state.x - cx) + abs(state.y - cy)
                       for cx, cy in cluster) / 3.0
        else:
            if not finish_coords:
                return 0.0
            return min(abs(state.x - fx) + abs(state.y - fy)
                       for fx, fy in finish_coords) / 3.0

    def astar_search_ordered(self, start_state,
                              checkpoint_clusters: list,
                              finish_coords: list):
        """
        Single-pass A* over the augmented state space (x, y, vx, vy, cp_idx).

        Checkpoint advancement
        ----------------------
        When the successor position (nx, ny) falls inside
        cp_sets[current.cp_idx], the successor is created with
        cp_idx + 1, recording that checkpoint as cleared.

        Hard finish-line constraint
        ---------------------------
        Finish tiles (grid value 3) are BLOCKED as long as
        cp_idx < num_cps.  This is the single-state equivalent of the
        old avoid_tile=3 parameter, extended to cover the whole search.

        Why this fixes the "wrong-way" bug
        -----------------------------------
        Going backwards around the circuit never advances cp_idx — the
        car would encounter future checkpoints (indices > cp_idx), not the
        current target.  The heuristic then pulls the search toward the
        correct next checkpoint, making the backwards path strictly more
        expensive.  The solver cannot short-circuit to the finish without
        clearing all checkpoints first.

        Returns (path_as_car_states, explored_as_car_states) or (None, explored).
        The return type matches what main.py expects from solve().
        """
        num_cps    = len(checkpoint_clusters)
        finish_set = {(int(x), int(y)) for x, y in finish_coords}

        # Pre-build O(1) membership sets — avoids linear scans per expansion
        cp_sets = [
            {(int(cx), int(cy)) for cx, cy in cluster}
            for cluster in checkpoint_clusters
        ]

        start = OrderedCarState.from_car_state(start_state, cp_idx=0)
        pq          = PriorityQueue()
        counter     = 0
        pq.put((0, counter, start))
        came_from   = {start: None}
        cost_so_far = {start: 0}
        explored    = []

        while not pq.empty():
            _, _, current = pq.get()
            explored.append(current.to_car_state())

            # ── Goal test ─────────────────────────────────────────────────────
            if (current.cp_idx == num_cps
                    and (current.x, current.y) in finish_set):
                return (self._reconstruct_ordered_path(came_from, current),
                        explored)

            # ── Expand ────────────────────────────────────────────────────────
            base = current.to_car_state()
            for nxt_car in self.engine.get_legal_moves(base):
                nx, ny = nxt_car.x, nxt_car.y
                tile   = self.engine.track[ny][nx]

                # Determine cp_idx advancement
                new_cp = current.cp_idx
                if new_cp < num_cps and (nx, ny) in cp_sets[new_cp]:
                    new_cp += 1

                # Hard constraint: finish is invisible until all CPs cleared
                if tile == 3 and new_cp < num_cps:
                    continue

                nxt = OrderedCarState(nx, ny, nxt_car.vx, nxt_car.vy, new_cp)

                new_cost = cost_so_far[current] + 1
                if nxt not in cost_so_far or new_cost < cost_so_far[nxt]:
                    cost_so_far[nxt] = new_cost
                    h = self._heuristic_ordered(
                        nxt, checkpoint_clusters, finish_coords, num_cps)
                    counter += 1
                    pq.put((new_cost + h, counter, nxt))
                    came_from[nxt] = current

        return None, explored   # unreachable track

    def _reconstruct_ordered_path(self, came_from: dict,
                                   current: OrderedCarState) -> list:
        """Back-trace from goal; return list of CarState objects."""
        path = []
        node = current
        while node is not None:
            path.append(node.to_car_state())
            node = came_from[node]
        path.reverse()
        return path

    # ── Fixed pipeline (BFS comparison only) ──────────────────────────────────

    def _solve_pipeline(self, start_state,
                         checkpoint_clusters: list,
                         finish_coords: list,
                         use_bfs: bool = True):
        """
        Original sequential pipeline, corrected.

        BUG FIXED: the finish-line hunt now runs ONCE, after ALL
        checkpoints have been cleared — not after each individual
        checkpoint as in the original code.

        Used only for BFS comparison.  A* now uses astar_search_ordered().
        """
        full_path    = []
        all_explored = []
        current_start = start_state
        search = self.bfs_search if use_bfs else self.astar_search

        # Phase 1: clear all checkpoints in sequence
        for idx, target_cluster in enumerate(checkpoint_clusters):
            segment, explored = search(
                current_start, target_cluster, avoid_tile=3)
            all_explored.extend(explored)
            if not segment:
                print(f"[PIPELINE] Cannot reach checkpoint {idx}.")
                return [], all_explored
            full_path     += segment[1:] if full_path else segment
            current_start  = segment[-1]

        # Phase 2: reach finish (now allowed — all CPs cleared)
        segment, explored = search(
            current_start, finish_coords, avoid_tile=None)
        all_explored.extend(explored)
        if not segment:
            print("[PIPELINE] Cannot reach finish line.")
            return full_path, all_explored
        full_path += segment[1:] if full_path else segment
        return full_path, all_explored

    # ── Public entry point (interface unchanged) ──────────────────────────────

    def solve(self, start_state, checkpoint_clusters: list,
              use_bfs: bool = False):
        """
        Compute the full optimal race path.

        A* branch  -> astar_search_ordered() — augmented state space,
                      single pass, checkpoint-ordered, no backtracking.
        BFS branch -> _solve_pipeline()      — sequential pipeline,
                      direction-agnostic (used only for metric comparison).

        Returns (full_path, all_explored, solve_time)
        — identical signature to the original, so main.py is unchanged.
        """
        print("--- STARTING SOLVER ---")
        start_time = time.time()

        # Build finish coords once
        finish_coords = [
            (x, y)
            for y in range(self.rows)
            for x in range(self.cols)
            if self.engine.track[y][x] == 3
        ]

        if not finish_coords:
            print("WARNING: No finish line found on this track.")
            return [], [], 0.0

        if use_bfs:
            full_path, all_explored = self._solve_pipeline(
                start_state, checkpoint_clusters,
                finish_coords, use_bfs=True)
        else:
            result = self.astar_search_ordered(
                start_state, checkpoint_clusters, finish_coords)
            if result[0] is None:
                full_path, all_explored = [], result[1]
            else:
                full_path, all_explored = result

        solve_time = time.time() - start_time

        print(f"  Path: {len(full_path)} steps | "
              f"Explored: {len(all_explored)} states | "
              f"Time: {solve_time:.3f}s")

        return full_path, all_explored, solve_time

    # ── Cluster extraction ────────────────────────────────────────────────────

    def _get_clusters(self, tile_value: int) -> list:
        """Group all tiles of a given value into 8-connected islands."""
        all_pixels = {
            (x, y)
            for y in range(self.rows)
            for x in range(self.cols)
            if self.engine.track[y][x] == tile_value
        }
        clusters = []
        while all_pixels:
            seed            = next(iter(all_pixels))
            current_cluster = {seed}
            queue           = [seed]
            all_pixels.discard(seed)
            while queue:
                cx, cy = queue.pop(0)
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1),
                                (-1,-1),(-1,1),(1,-1),(1,1)]:
                    nb = (cx + dx, cy + dy)
                    if nb in all_pixels:
                        all_pixels.discard(nb)
                        current_cluster.add(nb)
                        queue.append(nb)
            clusters.append(list(current_cluster))
        return clusters

    # ── Path reconstruction (base states) ────────────────────────────────────

    def _reconstruct_path(self, came_from: dict, current) -> list:
        path = []
        while current is not None:
            path.append(current)
            current = came_from[current]
        path.reverse()
        return path