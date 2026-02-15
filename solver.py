from queue import PriorityQueue
from car import CarState
import math

class AStarSolver:
    def __init__(self, engine):
        self.engine = engine
        self.cols = engine.cols
        self.rows = engine.rows
        
        self.current_goals = [] #generic list to accomodate checkpoints        for y in range(self.rows):
            for x in range(self.cols):
                if self.engine.track[y][x] == 3: # 3 is Finish Line
                    self.current_goals.append((x, y))
    
    def set_goals(self, tile_value):
        """Updates list of target coordinates based on tile type"""
        self.current_goals = []
        for y in range(self.rows):
            for x in range(self.cols):
                if self.engine.track[y][x] == tile_value:
                    self.current_goals.append((x, y))

    def heuristic(self, state):
        """
        Estimates the cost to reach the finish line.
        Uses 'Manhattan Distance' (generic grid distance).
        """
        if not self.current_goals:
            return 0
        
        # Find the distance to the CLOSEST finish tile
        min_dist = float('inf')
        for (gx, gy) in self.current_goals:
            dist = abs(state.x - gx) + abs(state.y - gy)
            if dist < min_dist:
                min_dist = dist
        
        # Divide by a "max speed" factor (e.g., 3) to make the heuristic admissible.
        # Prevents the AI from overestimating the cost.
        return min_dist / 3.0 
    def _get_clusters(self, tile_value):
        """
        Scans the grid and groups connected pixels into separate 'islands'.
        Returns a list of clusters: [ [(x1,y1), (x2,y2)], [(x3,y3)...] ]
        """
        # 1. Find ALL pixels of this color
        all_pixels = set()
        for y in range(self.rows):
            for x in range(self.cols):
                if self.engine.track[y][x] == tile_value:
                    all_pixels.add((x, y))
        
        clusters = []
        
        # 2. Group using Flood Fill (Breadth-First Search)
        while all_pixels:
            # Pick a random pixel to start a new cluster
            start_node = list(all_pixels)[0]
            current_cluster = {start_node}
            queue = [start_node]
            all_pixels.remove(start_node)
            
            while queue:
                cx, cy = queue.pop(0)
                # Check 4 neighbors (Up, Down, Left, Right)
                for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                    nx, ny = cx + dx, cy + dy
                    if (nx, ny) in all_pixels:
                        all_pixels.remove((nx, ny))
                        current_cluster.add((nx, ny))
                        queue.append((nx, ny))
            
            clusters.append(list(current_cluster))
            
        print(f"  > Detected {len(clusters)} Checkpoint Islands for value {tile_value}.")
        return clusters

    def set_goals_from_list(self, coords_list):
        """Directly sets the target pixels from a list of (x,y) tuples"""
        self.current_goals = coords_list

    def astar_search(self, start_state, target_coords):
        self.set_goals_from_list(target_coords)
        
        if not self.current_goals:
            return None

        queue = PriorityQueue()
        queue.put((0, 0, start_state))
        came_from = {start_state: None}
        cost_so_far = {start_state: 0}
        steps_explored = 0

        while not queue.empty():
            _, _, current = queue.get()
            steps_explored += 1

            # UPDATE CHECK: Is current position in  target list?
            if (current.x, current.y) in self.current_goals: 
                return self._reconstruct_path(came_from, current)

            for next_state in self.engine.get_legal_moves(current):
                new_cost = cost_so_far[current] + 1
                if next_state not in cost_so_far or new_cost < cost_so_far[next_state]:
                    cost_so_far[next_state] = new_cost
                    priority = new_cost + self.heuristic(next_state)
                    queue.put((priority, steps_explored, next_state))
                    came_from[next_state] = current
        return None

    def solve(self, start_state):
        print("--- STARTING SMART CHECKPOINT SOLVER ---")
        
        # 1. Detect all Yellow Checkpoints (Value 4)
        checkpoints = self._get_clusters(4) # Returns list of lists
        
        full_path = []
        current_start = start_state
        checkpoint_counter = 1

        # 2. Visit Checkpoints one by one (Greedy Nearest Neighbor)
        while checkpoints:
            # Find which cluster is closest to our CURRENT position
            best_cluster = None
            min_dist = float('inf')
            
            for cluster in checkpoints:
                # Calculate distance from car to the first pixel of this cluster
                cx, cy = cluster[0]
                dist = abs(current_start.x - cx) + abs(current_start.y - cy)
                if dist < min_dist:
                    min_dist = dist
                    best_cluster = cluster
            
            print(f"Heading to Checkpoint {checkpoint_counter}...")
            
            # Go to that checkpoint
            segment = self.astar_search(current_start, best_cluster)
            
            if not segment:
                print(f"Error: Could not reach Checkpoint {checkpoint_counter}!")
                return []
            
            # Add to path
            if full_path:
                full_path += segment[1:]
            else:
                full_path += segment
                
            # Update state
            current_start = segment[-1]
            checkpoints.remove(best_cluster) # Mark as "Done"
            print(f"Checkpoint {checkpoint_counter} Cleared!")
            checkpoint_counter += 1

        # 3. Finally, go to Finish (Green - Value 3)
        print("All checkpoints done. Heading to Finish (Green)...")
        
        finish_pixels = []
        for y in range(self.rows):
            for x in range(self.cols):
                if self.engine.track[y][x] == 3:
                    finish_pixels.append((x, y))
                    
        final_segment = self.astar_search(current_start, finish_pixels)
        
        if not final_segment:
            print("Error: Could not reach Finish line.")
            return []

        if full_path:
            full_path += final_segment[1:]
        else:
            full_path += final_segment
            
        print(f"RACE COMPLETE! Total Time: {len(full_path)} steps.")
        return full_path

    def _reconstruct_path(self, came_from, current):
        """Backtracks from the goal to the start to build the list of moves"""
        path = []
        while current is not None:
            path.append(current)
            current = came_from[current]
        path.reverse() # Reverse so it starts from the beginning
        return path