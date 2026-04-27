"""
solver.py
---------

"""

import heapq
from car import CarState
import time


# ═══════════════════════════════════════════════════════════════════════════════
# OrderedCarState  
# ═══════════════════════════════════════════════════════════════════════════════

class OrderedCarState:
    """
    (x, y, vx, vy, cp_idx) — extends CarState with the index of the next
    required checkpoint.
    """
    __slots__ = ('x', 'y', 'vx', 'vy', 'cp_idx')

    def __init__(self, x: int, y: int, vx: int, vy: int, cp_idx: int = 0):
        self.x      = x;  self.y      = y
        self.vx     = vx; self.vy     = vy
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
# AStarSolver
# ═══════════════════════════════════════════════════════════════════════════════

class AStarSolver:

    def __init__(self, engine):
        self.engine = engine
        self.cols   = engine.cols
        self.rows   = engine.rows
        self.current_goals: list = []

    # ── Heuristic (single-target) ───────────────────────────


    """def heuristic(self, state) -> float:
        
        Chebyshev distance to nearest goal tile / max_speed.

       
        if not self.current_goals:
            return 0.0
        max_speed = self.engine.max_speed
        return min(
            max(abs(state.x - gx), abs(state.y - gy))
            for gx, gy in self.current_goals
        ) / max_speed
    """
    # ═══════════════════════════════════════════════════════════════════════════
    # Single-target A*  (used by GA fitness)
    # ═══════════════════════════════════════════════════════════════════════════

    def astar_search(self, start_state, target_coords: list,
                     avoid_tile: int | None = None,
                     node_limit: int | None = None):
        """
        Optimised A* to a single target set.
        """
        if not target_coords:
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
            if node_limit is not None and len(explored) > node_limit:
                break   # chromosome likely unsolvable — return None for fitness = 0
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

    # ═══════════════════════════════════════════════════════════════════════════
    # Single-target BFS  (used for metric comparison)
    # ═══════════════════════════════════════════════════════════════════════════

    def bfs_search(self, start_state, target_coords: list,
                   avoid_tile: int | None = None):
        """
        Uninformed BFS expressed as uniform-cost Dijkstra via heapq
        """
        if not target_coords:
            return None, []

        goal_set   = frozenset((int(gx), int(gy)) for gx, gy in target_coords)
        _track     = self.engine.track
        _get_moves = self.engine.get_legal_moves
        _avoid     = avoid_tile
        _INF       = 10 ** 9

        start_key  = (start_state.x, start_state.y,
                      start_state.vx, start_state.vy)

        # heap entry: (g, counter, key) — no heuristic term
        heap      = [(0, 0, start_key)]
        g_score   = {start_key: 0}
        came_from = {start_key: None}
        explored  = []
        counter   = 1

        _heappush = heapq.heappush
        _heappop  = heapq.heappop

        while heap:
            g, _, cur = _heappop(heap)

            if g > g_score.get(cur, _INF):
                continue

            explored.append(cur)
            x, y, vx, vy = cur

            if (x, y) in goal_set:
                path = []
                node = cur
                while node is not None:
                    path.append(CarState(node[0], node[1], node[2], node[3]))
                    node = came_from[node]
                path.reverse()
                expl = [CarState(s[0], s[1], s[2], s[3]) for s in explored]
                return path, expl

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
                    _heappush(heap, (new_g, counter, nxt_key))
                    counter += 1

        expl = [CarState(s[0], s[1], s[2], s[3]) for s in explored]
        return None, expl

    # ═══════════════════════════════════════════════════════════════════════════
    # Checkpoint-ordered A*  (main race solver)
    # ═══════════════════════════════════════════════════════════════════════════

    def _heuristic_ordered(self, state, checkpoint_clusters, finish_coords, num_cps):
        """Legacy interface — now delegates to the admissible Chebyshev form."""
        max_speed = self.engine.max_speed
        if state.cp_idx < num_cps:
            cluster = checkpoint_clusters[state.cp_idx]
            return min(
                max(abs(state.x - cx), abs(state.y - cy))
                for cx, cy in cluster
            ) / max_speed                        # Chebyshev / v_max — admissible
        if not finish_coords:
            return 0.0
        return min(
            max(abs(state.x - fx), abs(state.y - fy))
            for fx, fy in finish_coords
        ) / max_speed

    def astar_search_ordered(self, start_state,
                              checkpoint_clusters: list,
                              finish_coords: list):
        """
        Optimised single-pass A* over the augmented 5-D state space
        (x, y, vx, vy, cp_idx).

        """
        num_cps    = len(checkpoint_clusters)
        max_speed  = self.engine.max_speed
        _track     = self.engine.track          # ← LOAD_FAST in inner loop
        _get_moves = self.engine.get_legal_moves
        _INF       = 10 ** 9

        # ── Pre-computation (once, before the hot loop) ───────────────────────

        finish_set = frozenset((int(x), int(y)) for x, y in finish_coords)
        if not finish_set:
            print("WARNING: No finish line found on this track.")
            return None, []

        # O(1) membership sets for checkpoint advancement
        cp_sets = [
            frozenset((int(cx), int(cy)) for cx, cy in cluster)
            for cluster in checkpoint_clusters
        ]

        # Axis-aligned bounding box per checkpoint + finish
        # Allows O(1) admissible heuristic without scanning cluster tiles
        def _bbox(coords):
            xs = [x for x, _ in coords]
            ys = [y for _, y in coords]
            return (min(xs), max(xs), min(ys), max(ys))

        cp_bbox  = [_bbox(cluster) for cluster in checkpoint_clusters]
        fin_bbox = _bbox(finish_coords)

        # Tie-breaking multiplier: (1+ε) biases equal-f nodes toward goal.
        TIE = 1.0 + 1e-4

        def _h(x: int, y: int, cp_idx: int) -> float:
            """
            Admissible O(1) heuristic with tie-breaking
            """
            bx_min, bx_max, by_min, by_max = (
                cp_bbox[cp_idx] if cp_idx < num_cps else fin_bbox)
            dx = max(0, bx_min - x, x - bx_max)
            dy = max(0, by_min - y, y - by_max)
            return max(dx, dy) / max_speed * TIE

        # ── Search initialisation ─────────────────────────────────────────────
        # State key: (x, y, vx, vy, cp_idx) — plain 5-tuple
        sx, sy   = start_state.x, start_state.y
        svx, svy = start_state.vx, start_state.vy
        start    = (sx, sy, svx, svy, 0)
        h0       = _h(sx, sy, 0)

        # heap entry: (f, g, counter, state_key)
        # counter guarantees stable ordering when f and g are identical,
        # making tie-breaking deterministic and preventing tuple comparison
        # from ever reaching the state key itself.
        heap      = [(h0, 0, 0, start)]
        g_score   = {start: 0}
        came_from = {start: None}
        explored  = []      # raw tuple states; converted to CarState at return
        counter   = 1

        _heappush = heapq.heappush   # bind to local for LOAD_FAST
        _heappop  = heapq.heappop

        # ── Main search loop ──────────────────────────────────────────────────
        while heap:
            f, g, _, cur = _heappop(heap)

            # The cost stored in g_score is always the best known cost; if the
            # popped g is larger, this entry is outdated and can be skipped.
            if g > g_score.get(cur, _INF):
                continue

            x, y, vx, vy, cp_idx = cur
            explored.append(cur)

            # ── Goal test ─────────────────────────────────────────────────────
            if cp_idx == num_cps and (x, y) in finish_set:
                # Back-trace the came_from chain
                path = []
                node = cur
                while node is not None:
                    path.append(CarState(node[0], node[1], node[2], node[3]))
                    node = came_from[node]
                path.reverse()
                expl = [CarState(s[0], s[1], s[2], s[3]) for s in explored]
                return path, expl

            # ── Expand: generate successors ───────────────────────────────────
            proxy = CarState(x, y, vx, vy)  # temporary proxy for get_legal_moves
            for nxt_car in _get_moves(proxy):
                nx, ny   = nxt_car.x,  nxt_car.y
                nvx, nvy = nxt_car.vx, nxt_car.vy

                tile   = _track[ny][nx]   # LOAD_FAST — bound above the loop

                # Determine cp_idx advancement for this successor
                new_cp = cp_idx
                if new_cp < num_cps and (nx, ny) in cp_sets[new_cp]:
                    new_cp += 1

                # Hard finish constraint: finish is invisible until all CPs cleared
                if tile == 3 and new_cp < num_cps:
                    continue

                nxt   = (nx, ny, nvx, nvy, new_cp)
                new_g = g + 1

                # Lazy-update: only push if this path is strictly cheaper
                if new_g < g_score.get(nxt, _INF):
                    g_score[nxt]   = new_g
                    came_from[nxt] = cur
                    h_val          = _h(nx, ny, new_cp)
                    _heappush(heap, (new_g + h_val, new_g, counter, nxt))
                    counter += 1

        # No path found (track is unsolvable from start_state)
        expl = [CarState(s[0], s[1], s[2], s[3]) for s in explored]
        return None, expl

   

    # ── Fixed pipeline (BFS comparison only) ─────────────────────────────────

    def _solve_pipeline(self, start_state,
                         checkpoint_clusters: list,
                         finish_coords: list,
                         use_bfs: bool = True):
        """
        Sequential pipeline.

        Used exclusively for the BFS metric comparison so that both solvers
        navigate the same checkpoint sequence.
        """
        full_path    = []
        all_explored = []
        current_start = start_state
        search = self.bfs_search if use_bfs else self.astar_search

        for idx, target_cluster in enumerate(checkpoint_clusters):
            segment, explored = search(
                current_start, target_cluster, avoid_tile=3)
            all_explored.extend(explored)
            if not segment:
                print(f"[PIPELINE] Cannot reach checkpoint {idx}.")
                return [], all_explored
            full_path    += segment[1:] if full_path else segment
            current_start = segment[-1]

        segment, explored = search(
            current_start, finish_coords, avoid_tile=None)
        all_explored.extend(explored)
        if not segment:
            print("[PIPELINE] Cannot reach finish line.")
            return full_path, all_explored
        full_path += segment[1:] if full_path else segment
        return full_path, all_explored

    # ── Public entry point ────────────────────────────────────────────────────

    def solve(self, start_state, checkpoint_clusters: list,
              use_bfs: bool = False):
        """
        Compute the full optimal race path.
        """
        print("--- STARTING SOLVER ---")
        start_time = time.time()

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
        from collections import deque
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
            queue           = deque([seed])   # O(1) popleft vs O(n) list.pop(0)
            all_pixels.discard(seed)
            while queue:
                cx, cy = queue.popleft()
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1),
                                (-1,-1),(-1,1),(1,-1),(1,1)]:
                    nb = (cx + dx, cy + dy)
                    if nb in all_pixels:
                        all_pixels.discard(nb)
                        current_cluster.add(nb)
                        queue.append(nb)
            clusters.append(list(current_cluster))
        return clusters