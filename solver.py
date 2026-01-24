from queue import PriorityQueue
from car import CarState
import math

class AStarSolver:
    def __init__(self, engine):
        self.engine = engine
        self.cols = engine.cols
        self.rows = engine.rows
        
        # Find all goal (finish line) positions
        self.goals = []
        for y in range(self.rows):
            for x in range(self.cols):
                if self.engine.track[y][x] == 3: # 3 is Finish Line
                    self.goals.append((x, y))

    def heuristic(self, state):
        """
        Estimates the cost to reach the finish line.
        Uses 'Manhattan Distance' (generic grid distance).
        """
        if not self.goals:
            return 0
        
        # Find the distance to the CLOSEST finish tile
        min_dist = float('inf')
        for (gx, gy) in self.goals:
            dist = abs(state.x - gx) + abs(state.y - gy)
            if dist < min_dist:
                min_dist = dist
        
        # We divide by a "max speed" factor (e.g., 3) to make the heuristic admissible.
        # This prevents the AI from overestimating the cost.
        return min_dist / 3.0 

    def solve(self, start_state):
        print("AI is calculating path... (This might take a moment)")
        
        # Priority Queue stores: (f_score, step_count, current_state)
        # step_count is a tie-breaker so Python doesn't crash comparing states
        queue = PriorityQueue()
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

            # Check if we hit the finish line (Value 3)
            if self.engine.track[current.y][current.x] == 3:
                print(f"Goal found! Explored {steps_explored} states.")
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