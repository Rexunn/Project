from car import CarState
import math

class PhysicsEngine:
    def __init__(self, track_grid):
        self.track = track_grid
        self.rows = len(track_grid)
        self.cols = len(track_grid[0])
        
        #state switch system
        self.lethal_tiles = {0} 

    def set_lethal(self, tile_value, is_lethal):
        if is_lethal:
            self.lethal_tiles.add(tile_value)
        else:
            self.lethal_tiles.discard(tile_value)

    def get_legal_moves(self, current_state):
        next_states = []
        #acceleration options (brake, coast, gas)
        acceleration_options = [-1, 0, 1]

        for ax in acceleration_options:
            for ay in acceleration_options:
                new_vx = current_state.vx + ax
                new_vy = current_state.vy + ay
                
                #limit max speed to prevent huge jumps (optional but good for stability)
                #if new_vx > 5: new_vx = 5
                
                new_x = current_state.x + new_vx
                new_y = current_state.y + new_vy
                
                #NEW: check the full path, not just the end point
                if self._check_path_safety(current_state.x, current_state.y, new_x, new_y):
                    new_state = CarState(new_x, new_y, new_vx, new_vy)
                    next_states.append(new_state)
        
        return next_states

    def _check_path_safety(self, x1, y1, x2, y2):
        """
        uses Bresenham's line algorithm logic to check if a wall exists
        BETWEEN point A and point B. prevents tunneling through thin walls.
        """
        #check destination first (fastest fail)
        if not self._is_safe_pixel(x2, y2): return False

        #how far are we moving?
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        steps = max(dx, dy) #number of pixels to check
        
        if steps == 0: return True

        #sample points along the line
        for i in range(1, steps + 1):
            t = i / steps
            xt = int(x1 + t * (x2 - x1))
            yt = int(y1 + t * (y2 - y1))
            
            if not self._is_safe_pixel(xt, yt):
                return False #hit a wall mid-move!
        
        return True

    def _is_safe_pixel(self, x, y):
        #bounds check
        if x < 0 or x >= self.cols or y < 0 or y >= self.rows:
            return False
        #lethal tile check
        if self.track[y][x] in self.lethal_tiles: 
            return False
        return True