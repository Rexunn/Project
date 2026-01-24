import pygame
import settings as s
from track import Track
from game_engine import PhysicsEngine
from car import CarState
from solver import AStarSolver # <--- IMPORT THE AI

def main():
    pygame.init()
    screen = pygame.display.set_mode((s.screen_width, s.screen_height))
    pygame.display.set_caption("Phase 3: AI Solver Prototype")
    clock = pygame.time.Clock()

    # --- 1. SETUP ---
    track = Track("track.png")
    engine = PhysicsEngine(track.grid)
    
    # Find Start Position
    start_x, start_y = 5, 5
    for r in range(track.rows):
        for c in range(track.cols):
            if track.grid[r][c] == 2: # Start
                start_x, start_y = c, r
                break

    start_state = CarState(start_x, start_y, 0, 0)
    car = start_state

    # --- 2. AI CALCULATION ---
    # We solve the path BEFORE the game loop starts
    solver = AStarSolver(engine)
    path = solver.solve(start_state)
    
    path_index = 0 # Keeps track of which step we are showing
    
    # --- 3. ANIMATION LOOP ---
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # AUTO-PLAY LOGIC
        # Every few frames, move to the next step in the AI's path
        if path and path_index < len(path):
            # Slow down the replay so we can see it (only update every 5 ticks)
            # OR just update every frame if you want it fast
            car = path[path_index]
            path_index += 1
            pygame.time.delay(100) # Simple delay to make it watchable
        
        # --- DRAWING ---
        screen.fill(s.gray) # Red background
        track.draw(screen)  # Draw Black Track + Start/Finish
        
        # Draw Car
        pixel_x = car.x * track.TILE_SIZE + (track.TILE_SIZE // 2)
        pixel_y = car.y * track.TILE_SIZE + (track.TILE_SIZE // 2)
        
        pygame.draw.circle(screen, s.white, (pixel_x, pixel_y), track.TILE_SIZE // 2)
        
        # Draw Path History (Optional: draw dots where the car will go)
        for step in path:
            px = step.x * track.TILE_SIZE + (track.TILE_SIZE // 2)
            py = step.y * track.TILE_SIZE + (track.TILE_SIZE // 2)
            pygame.draw.circle(screen, (255, 255, 0), (px, py), 2)

        pygame.display.flip()
        clock.tick(s.fps)

    pygame.quit()

if __name__ == "__main__":
    main()