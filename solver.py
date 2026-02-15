from queue import PriorityQueue
from car import CarState
import math

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
        return min_dist / 3.0 

    def _get_clusters(self, tile_value):
        """groups connected pixels into separate checkpoints"""
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
                for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                    nx, ny = cx + dx, cy + dy
                    if (nx, ny) in all_pixels:
                        all_pixels.remove((nx, ny))
                        current_cluster.add((nx, ny))
                        queue.append((nx, ny))
            clusters.append(list(current_cluster))
        
        #debug print
        print(f"DEBUG: Found {len(clusters)} checkpoint islands.")
        return clusters

    def astar_search(self, start_state, target_coords, avoid_tile=None):
        self.set_goals_from_list(target_coords)
        if not self.current_goals: return None

        queue = PriorityQueue()
        queue.put((0, 0, start_state))
        came_from = {start_state: None}
        cost_so_far = {start_state: 0}

        while not queue.empty():
            _, _, current = queue.get()
            
            #check if we hit target
            if (current.x, current.y) in self.current_goals: 
                return self._reconstruct_path(came_from, current)

            for next_state in self.engine.get_legal_moves(current):
                #NEW: check for avoidance tile (e.g. dont cross finish line backwards)
                if avoid_tile is not None:
                     if self.engine.track[next_state.y][next_state.x] == avoid_tile:
                         continue #treat as wall

                new_cost = cost_so_far[current] + 1
                if next_state not in cost_so_far or new_cost < cost_so_far[next_state]:
                    cost_so_far[next_state] = new_cost
                    priority = new_cost + self.heuristic(next_state)
                    queue.put((priority, 0, next_state))
                    came_from[next_state] = current
        return None

    def solve(self, start_state):
        print("--- STARTING SOLVER ---")
        
        #phase 1: hunt yellow checkpoints
        checkpoints = self._get_clusters(4) 
        
        full_path = []
        current_start = start_state
        
        while checkpoints:
            #find nearest cluster
            best_cluster = None
            min_dist = float('inf')
            for cluster in checkpoints:
                cx, cy = cluster[0]
                dist = abs(current_start.x - cx) + abs(current_start.y - cy)
                if dist < min_dist:
                    min_dist = dist
                    best_cluster = cluster
            
            print("Heading to Checkpoint (Avoiding Finish Line)...")
            
            #pass avoid_tile=3 (Green) so car doesn't shortcut through finish
            segment = self.astar_search(current_start, best_cluster, avoid_tile=3)
            
            if not segment: 
                print("Error: Path blocked or checkpoint unreachable.")
                return []
            
            full_path += segment[1:] if full_path else segment
            current_start = segment[-1]
            checkpoints.remove(best_cluster)

        #phase 2: hunt finish (green)
        print("Checkpoints cleared. Heading to Finish.")
        finish_pixels = []
        for y in range(self.rows):
            for x in range(self.cols):
                if self.engine.track[y][x] == 3:
                    finish_pixels.append((x, y))
                    
        #allow crossing finish line now (avoid_tile=None)
        final_segment = self.astar_search(current_start, finish_pixels, avoid_tile=None)
        return full_path + final_segment[1:] if final_segment else full_path

    def _reconstruct_path(self, came_from, current):
        path = []
        while current is not None:
            path.append(current)
            current = came_from[current]
        path.reverse()
        return path