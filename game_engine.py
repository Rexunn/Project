from car import CarState
import math

class PhysicsEngine:
    def __init__(self, track_grid):
        self.track = track_grid
        self.rows = len(track_grid)
        self.cols = len(track_grid[0])
        self.lethal_tiles = {0} #0 is wall

    def get_legal_moves(self, current_state):
        next_states = []
        acceleration_options = [-1, 0, 1]

        for ax in acceleration_options:
            for ay in acceleration_options:
                new_vx = current_state.vx + ax
                new_vy = current_state.vy + ay
                
                #cap max speed to prevent glitches
                if new_vx > 5: new_vx = 5
                if new_vx < -5: new_vx = -5
                if new_vy > 5: new_vy = 5
                if new_vy < -5: new_vy = -5

                new_x = current_state.x + new_vx
                new_y = current_state.y + new_vy
                
                #check full path, not just endpoint
                if self._check_path(current_state.x, current_state.y, new_x, new_y):
                    new_state = CarState(new_x, new_y, new_vx, new_vy)
                    next_states.append(new_state)
        return next_states

    def _check_path(self, x1, y1, x2, y2):
        #bresenham's line algorithm to stop tunneling
        if not self._is_safe(x2, y2): return False

        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        steps = max(dx, dy) 
        
        if steps == 0: return True

        for i in range(1, steps + 1):
            t = i / steps
            xt = int(x1 + t * (x2 - x1))
            yt = int(y1 + t * (y2 - y1))
            
            if not self._is_safe(xt, yt):
                return False 
        return True

    def _is_safe(self, x, y):
        #bounds check
        if x < 0 or x >= self.cols or y < 0 or y >= self.rows: return False
        #wall check
        if self.track[y][x] in self.lethal_tiles: return False
        return True