from car import CarState

class PhysicsEngine:
    def __init__(self, track_grid):
        self.track = track_grid
        self.rows = len(track_grid)
        self.cols = len(track_grid[0])
        
        #state switch system - used to toggle traps/walls
        #any tile in this set kills the car
        #default: 0 is wall. we can add '5' for spikes later
        self.lethal_tiles = {0} 

    def set_lethal(self, tile_value, is_lethal):
        """
        turns a tile type ON (deadly) or OFF (safe)
        """
        if is_lethal:
            self.lethal_tiles.add(tile_value)
        else:
            self.lethal_tiles.discard(tile_value)

    def get_legal_moves(self, current_state):
        next_states = []
        acceleration_options = [-1, 0, 1]

        for ax in acceleration_options:
            for ay in acceleration_options:
                #calculate new velocity
                new_vx = current_state.vx + ax
                new_vy = current_state.vy + ay
                
                #calculate new position
                new_x = current_state.x + new_vx
                new_y = current_state.y + new_vy
                
                #validation check
                if self._is_valid(new_x, new_y):
                    new_state = CarState(new_x, new_y, new_vx, new_vy)
                    next_states.append(new_state)
        
        return next_states

    def _is_valid(self, x, y):
        #check boundaries
        if x < 0 or x >= self.cols or y < 0 or y >= self.rows:
            return False
            
        #check dynamic lethality
        #if tile is in kill list, it's a wall
        #otherwise it's safe (even if it's finish line or trap)
        if self.track[y][x] in self.lethal_tiles: 
            return False
            
        return True