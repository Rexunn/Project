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

    def astar_search(self, start_state, goal_tile_value):
        print("AI is calculating path... (This might take a moment)")
        
        self.set_goals(goal_tile_value)
        
        if not self.current_goals:
            print(f"Error: Target type {goal_tile_value} not found on track!")
            return None # Which pixels are we looking for

        # Standard A* setup
        queue = PriorityQueue()# (f_score, step_count, current_state) stepcount = tie-breaker so it doesn't crash comparing states
        queue.put((0, 0, start_state))
        # Came_from stores: {current_state: previous_state} to rebuild path later
        came_from = {}
        came_from[start_state] = None
        # Cost_so_far stores: {state: cost_to_get_here}
        cost_so_far = {}
        cost_so_far[start_state] = 0
        steps_explored = 0

        while not queue.empty():
            _, _, current = queue.get()
            steps_explored += 1

            # Check if we hit rquested tile)
            if self.engine.track[current.y][current.x] == goal_tile_value:
                #print(f"Goal found! Explored {steps_explored} states.")
                return self._reconstruct_path(came_from, current)

            # Get all valid next moves (Physics Engine logic)
            neighbors = self.engine.get_legal_moves(current)
            
            for next_state in neighbors:
                new_cost = cost_so_far[current] + 1 # Each move costs 1
                
                if next_state not in cost_so_far or new_cost < cost_so_far[next_state]:
                    cost_so_far[next_state] = new_cost
                    priority = new_cost + self.heuristic(next_state)
                    queue.put((priority, steps_explored, next_state))
                    came_from[next_state] = current

        print("No path found.")
        return []

    def _reconstruct_path(self, came_from, current):
        """Backtracks from the goal to the start to build the list of moves"""
        path = []
        while current is not None:
            path.append(current)
            current = came_from[current]
        path.reverse() # Reverse so it starts from the beginning
        return path