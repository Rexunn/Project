from car import CarState

class PhysicsEngine:
    def __init__(self, track_grid):
        """
        track_grid: A 2D list (grid[y][x]) where:
        0 = Wall/Grass (Crash)
        1 = Road (Safe)
        2 = Start
        3 = Finish
        """
        self.track = track_grid
        self.rows = len(track_grid)
        self.cols = len(track_grid[0])

    def get_legal_moves(self, current_state):
        """
        Returns a list of all valid CarState objects reachable from the current state.
        Considers all 9 possible acceleration combinations (-1, 0, 1).
        """
        next_states = []
        acceleration_options = [-1, 0, 1]

        for ax in acceleration_options:
            for ay in acceleration_options:
                #calculate new Velocity
                new_vx = current_state.vx + ax
                new_vy = current_state.vy + ay
                
                #calculate new Position
                new_x = current_state.x + new_vx
                new_y = current_state.y + new_vy
                
                #validation Check
                if self._is_valid(new_x, new_y):
                    new_state = CarState(new_x, new_y, new_vx, new_vy)
                    next_states.append(new_state)
        
        return next_states

    def _is_valid(self, x, y):
        """Internal helper to check boundaries and walls"""
        #check Boundaries
        if x < 0 or x >= self.cols or y < 0 or y >= self.rows:
            return False
            
        #check Wall Collision (0 is Wall)
        if self.track[y][x] == 0: 
            return False
            
        return True