import pygame

class Car:
    def _init_(self, start_pos, colour=(255, 0, 0)):
        #Core State
        self.position = pygame.Vector2(start_pos)
        self.velocity = pygame.Vector2(0, 0)
        
        #Visuals
        self.colour = colour
        self.radius = 5

        #History
        self.path = [self.position]
        self.last_safe_position = pygame.Vector2(start_pos)

    def update_velocity(self, dx_change, dy_change):
        """Applies acceleration"""
        self.velocity.x += dx_change
        self.velocity.y += dy_change
    
    def get_next_position(self):
        """Calculates where the car WILL GO"""
        return self.position + self.velocity

    def commit_move(self, new_postion):
        """Official Car position update"""
        self.position = pygame.Vector2(new_position)
        self.path.append(self.position)
        self.last_safe_position = pygame.Vector2(new_position)  #Stores good move
    
    def crash(self):
        """Resets velocity on crash and moves to last safe spot"""
        print("CRASH! Velocity reset, back to last safe position")
        self.velocity = pygame.Vector2(0, 0)
        self.position = self.last_safe_position  #go back
        self.path.append(self.position)  #add reset to path
        
    def draw(self, screen):
        #draw car path
        if len(self.path) > 1:
            #draw line
            pygame.draw.lines(screen, self.colour + (100,), False, self.path, 2)