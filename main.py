import pygame
import settings as s
from track import Track
from game_engine import PhysicsEngine
from car import CarState

def main():
    pygame.init()
    screen = pygame.display.set_mode((s.screen_width, s.screen_height))
    pygame.display.set_caption("Phase 2 Prototype: Grid Physics Test")
    clock = pygame.time.Clock()

    #load track
    track = Track("track.png")
    

    engine = PhysicsEngine(track.grid)
    
    #find start position
    start_x, start_y = 5, 5 # Default
    for r in range(track.rows):
        for c in range(track.cols):
            if track.grid[r][c] == 2:
                start_x, start_y = c, r
                break

    car = CarState(start_x, start_y, 0, 0)


    running = True
    while running:
        #controller
        action_taken = False
        ax, ay = 0, 0
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:  ax = -1
                if event.key == pygame.K_RIGHT: ax = 1
                if event.key == pygame.K_UP:    ay = -1
                if event.key == pygame.K_DOWN:  ay = 1
                
                # If a key was pressed, attempt a move
                if ax != 0 or ay != 0:
                    action_taken = True

        #model
        if action_taken:

            next_vx = car.vx + ax
            next_vy = car.vy + ay
            next_x = car.x + next_vx
            next_y = car.y + next_vy

            if engine._is_valid(next_x, next_y):
                car = CarState(next_x, next_y, next_vx, next_vy)
                print(f"Move Accepted: Pos({car.x}, {car.y}) Vel({car.vx}, {car.vy})")
            else:
                print("CRASH! Move invalid (Wall or Boundary)")
                #in real game, might reset the car here
                #car = CarState(start_x, start_y, 0, 0)

        #view
        screen.fill(s.gray) 
        #draw grid
        track.draw(screen)
        
        #draw car
        pixel_x = car.x * track.TILE_SIZE + (track.TILE_SIZE // 2)
        pixel_y = car.y * track.TILE_SIZE + (track.TILE_SIZE // 2)
        
        pygame.draw.circle(screen, s.red, (pixel_x, pixel_y), track.TILE_SIZE // 2)
        
        #draw velocity vector
        end_pos = (pixel_x + car.vx * track.TILE_SIZE, pixel_y + car.vy * track.TILE_SIZE)
        pygame.draw.line(screen, s.white, (pixel_x, pixel_y), end_pos, 2)

        pygame.display.flip()
        clock.tick(s.fps)

    pygame.quit()

if __name__ == "__main__":
    main()