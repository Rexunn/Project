from queue import PriorityQueue
from car import CarState
import math
import time

class AStarSolver:
    def __init__(self, engine):
        self.engine = engine
        self.cols = engine.cols
        self.rows = engine.rows
        self.current_goals = [] 

    def set_goals_from_list(self, coords_list):
        self.current_goals = coords_list

    def heuristic(self, state):
        if not self.current_goals: return 0
        min_dist = float('inf')
        for (gx, gy) in self.current_goals:
            dist = abs(state.x - gx) + abs(state.y - gy)
            if dist < min_dist: min_dist = dist
                # divide by 3.0 because the car's max speed cap is 5. 
               # Keeping this divisor ensures the heuristic remains "admissible"
        return min_dist / 3.0 

    def _get_clusters(self, tile_value):
        #groups pixels into separate islands (checkpoints)
        all_pixels = set()
        for y in range(self.rows):
            for x in range(self.cols):
                if self.engine.track[y][x] == tile_value:
                    all_pixels.add((x, y))
        
        clusters = []
        while all_pixels:
            start_node = list(all_pixels)[0]
            current_cluster = {start_node}
            queue = [start_node]
            all_pixels.remove(start_node)
            while queue:
                cx, cy = queue.pop(0)
                for dx, dy in [(-1,0), (1,0), (0,-1), (0,1), (-1,-1), (-1,1), (1,-1), (1,1)]:
                    nx, ny = cx + dx, cy + dy
                    if (nx, ny) in all_pixels:
                        all_pixels.remove((nx, ny))
                        current_cluster.add((nx, ny))
                        queue.append((nx, ny))
            clusters.append(list(current_cluster))
        return clusters

    def astar_search(self, start_state, target_coords, avoid_tile=None):
        self.set_goals_from_list(target_coords)
        if not self.current_goals: return None, []

        queue = PriorityQueue()
        queue.put((0, 0, start_state))
        came_from = {start_state: None}
        cost_so_far = {start_state: 0}
        explored_states = []  # Track all explored states for debug visualization

        while not queue.empty():
            _, _, current = queue.get()
            explored_states.append(current)  # Add to explored list

            #check target
            if (current.x, current.y) in self.current_goals:
                return self._reconstruct_path(came_from, current), explored_states

            for next_state in self.engine.get_legal_moves(current):
                #avoidance check (e.g. dont hit finish line yet)
                if avoid_tile is not None:
                     if self.engine.track[next_state.y][next_state.x] == avoid_tile:
                         continue

                new_cost = cost_so_far[current] + 1
                if next_state not in cost_so_far or new_cost < cost_so_far[next_state]:
                    cost_so_far[next_state] = new_cost
                    priority = new_cost + self.heuristic(next_state)
                    queue.put((priority, 0, next_state))
                    came_from[next_state] = current
        return None, explored_states

    def bfs_search(self, start_state, target_coords, avoid_tile=None):
        self.set_goals_from_list(target_coords)
        if not self.current_goals: return None, []

        queue = PriorityQueue()
        queue.put((0, 0, start_state))
        came_from = {start_state: None}
        cost_so_far = {start_state: 0}
        explored_states = []  # Track all explored states for debug visualization

        while not queue.empty():
            _, _, current = queue.get()
            explored_states.append(current)  # Add to explored list

            #check target
            if (current.x, current.y) in self.current_goals:
                return self._reconstruct_path(came_from, current), explored_states

            for next_state in self.engine.get_legal_moves(current):
                #avoidance check (e.g. dont hit finish line yet)
                if avoid_tile is not None:
                     if self.engine.track[next_state.y][next_state.x] == avoid_tile:
                         continue

                new_cost = cost_so_far[current] + 1
                if next_state not in cost_so_far or new_cost < cost_so_far[next_state]:
                    cost_so_far[next_state] = new_cost
                    priority = new_cost
                    queue.put((priority, 0, next_state))
                    came_from[next_state] = current
        return None, explored_states    

    def solve(self, start_state, use_bfs=False):
            print("--- STARTING SOLVER ---")
            start_time = time.time()

            full_path = []
            all_explored = []  
            current_start = start_state
            total_laps = 3

            for lap in range(total_laps):
                print(f"\n=== CALCULATING LAP {lap + 1}/{total_laps} ===")
                
                # phase 1: hunt yellow checkpoints
                checkpoints = self._get_clusters(4)
                checkpoint_num = 0
                
                while checkpoints:
                    checkpoint_num += 1
                    best_cluster = None
                    min_dist = float('inf')
                    for cluster in checkpoints:
                        cx, cy = cluster[0]
                        dist = abs(current_start.x - cx) + abs(current_start.y - cy)
                        if dist < min_dist:
                            min_dist = dist
                            best_cluster = cluster

                    # avoid finish line so we don't shortcut
                    if use_bfs:
                        segment, explored = self.bfs_search(current_start, best_cluster, avoid_tile=3)
                    else:
                        segment, explored = self.astar_search(current_start, best_cluster, avoid_tile=3)

                    all_explored.extend(explored) 

                    if not segment:
                        print("Error: Path to checkpoint blocked.")
                        return [], all_explored, 0

                    full_path += segment[1:] if full_path else segment
                    current_start = segment[-1]
                    checkpoints.remove(best_cluster)

                # phase 2: hunt finish (green)
                finish_pixels = []
                for y in range(self.rows):
                    for x in range(self.cols):
                        if self.engine.track[y][x] == 3:
                            finish_pixels.append((x, y))

                if not finish_pixels:
                    print("WARNING: No finish line found on track!")
                    return full_path, all_explored, 0

                # now allowed to cross finish line
                if use_bfs:
                    final_segment, final_explored = self.bfs_search(current_start, finish_pixels, avoid_tile=None)
                else:
                    final_segment, final_explored = self.astar_search(current_start, finish_pixels, avoid_tile=None)
                
                all_explored.extend(final_explored) 

                if not final_segment:
                    print("ERROR: Cannot find path to finish line!")
                    return full_path, all_explored, 0

                # Add this lap's finish line segment to the mega-path
                full_path += final_segment[1:] if full_path else final_segment
                # The exact state we crossed the finish line becomes the start state for the next lap!
                current_start = final_segment[-1] 

            print(f"\n=== 3-LAP PATH COMPLETE ===")
            print(f"Total path length: {len(full_path)} steps")
            print(f"Total states explored: {len(all_explored)}")
            solve_time = time.time() - start_time
            return full_path, all_explored, solve_time

    def _reconstruct_path(self, came_from, current):
        """Backtrack from goal to start"""
        path = []
        while current is not None:
            path.append(current)
            current = came_from[current]
        path.reverse()
        return path