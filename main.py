import pygame
import settings as s
from track import Track
from game_engine import PhysicsEngine
from car import CarState
from solver import AStarSolver

def draw_text(screen, text, size, color, x, y):
    font = pygame.font.SysFont("arial", size, bold=True)
    surface = font.render(text, True, color)
    rect = surface.get_rect(center=(x, y))
    screen.blit(surface, rect)

def main():
    pygame.init()
    screen = pygame.display.set_mode((s.screen_width, s.screen_height))
    pygame.display.set_caption("Racetrack AI Prototype")
    clock = pygame.time.Clock()

    # --- LOADING ASSETS ---
    track = Track("track.png")
    engine = PhysicsEngine(track.grid)
    
    # Find Start Position
    start_x, start_y = 5, 5
    found_start = False
    for r in range(track.rows):
        for c in range(track.cols):
            if track.grid[r][c] == 2: # Start
                start_x, start_y = c, r
                found_start = True
                break
    
    if not found_start:
        print("WARNING: No Blue Start Line found on track! AI will start at 5,5.")

    start_state = CarState(start_x, start_y, 0, 0)
    car = start_state
    
    # Game Variables
    game_state = "MENU" # MENU, LOADING, RUNNING, GAMEOVER
    path = []
    path_index = 0
    start_time = 0
    final_time = 0  # Store the time when goal is reached
    total_steps = 0
    total_checkpoints = 0
    checkpoints_visited = set()  # Track which checkpoint tiles we've visited

    running = True
    while running:
        # --- EVENT HANDLING ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if event.type == pygame.KEYDOWN:
                if game_state == "MENU" and event.key == pygame.K_SPACE:
                    game_state = "LOADING"
                elif game_state == "GAMEOVER" and event.key == pygame.K_SPACE:
                    # Reset for replay
                    car = start_state
                    path_index = 0
                    start_time = pygame.time.get_ticks()
                    checkpoints_visited = set()
                    game_state = "RUNNING"

        # --- LOGIC & DRAWING ---
        screen.fill(s.gray) # Background
        track.draw(screen)  # Draw Track
        
        if game_state == "MENU":
            # Darken the background slightly for menu readability
            overlay = pygame.Surface((s.screen_width, s.screen_height))
            overlay.set_alpha(128)
            overlay.fill((0,0,0))
            screen.blit(overlay, (0,0))
            
            draw_text(screen, "RACETRACK AI SOLVER", 60, s.white, s.screen_width//2, s.screen_height//2 - 50)
            draw_text(screen, "Press SPACE to Calculate Path", 30, s.white, s.screen_width//2, s.screen_height//2 + 20)

        elif game_state == "LOADING":
            # Draw one frame of "Loading..." before blocking calculation
            draw_text(screen, "Calculating Optimal Path...", 40, s.white, s.screen_width//2, s.screen_height//2)
            pygame.display.flip()

            # Count total checkpoints on track
            total_checkpoints = 0
            for r in range(track.rows):
                for c in range(track.cols):
                    if track.grid[r][c] == 4:  # Yellow checkpoint
                        total_checkpoints += 1

            # Run Solver
            solver = AStarSolver(engine)
            path = solver.solve(start_state)

            if not path:
                print("No Path Found!")
                game_state = "MENU" # Go back if failed
            else:
                total_steps = len(path)
                start_time = pygame.time.get_ticks()
                game_state = "RUNNING"

        elif game_state == "RUNNING":
            # Auto-replay the path
            if path and path_index < len(path):
                car = path[path_index]

                # Track checkpoint visits
                current_tile = track.grid[car.y][car.x]
                if current_tile == 4:  # Yellow checkpoint
                    checkpoints_visited.add((car.x, car.y))

                path_index += 1
                pygame.time.delay(100) # Speed control
            else:
                # Capture final time before transitioning to GAMEOVER
                final_time = (pygame.time.get_ticks() - start_time) / 1000.0
                game_state = "GAMEOVER"

            # Draw Car
            pixel_x = car.x * track.TILE_SIZE + (track.TILE_SIZE // 2)
            pixel_y = car.y * track.TILE_SIZE + (track.TILE_SIZE // 2)
            pygame.draw.circle(screen, s.white, (pixel_x, pixel_y), track.TILE_SIZE // 2)

            # Draw Path History (Yellow Dots)
            for i in range(path_index):
                step = path[i]
                px = step.x * track.TILE_SIZE + (track.TILE_SIZE // 2)
                py = step.y * track.TILE_SIZE + (track.TILE_SIZE // 2)
                pygame.draw.circle(screen, (255, 255, 0), (px, py), 2)

            # Display live stats
            elapsed_time = (pygame.time.get_ticks() - start_time) / 1000.0  # Convert to seconds
            draw_text(screen, f"Step: {path_index}/{total_steps}", 20, s.white, 80, 20)
            draw_text(screen, f"Time: {elapsed_time:.1f}s", 20, s.white, 80, 45)
            if total_checkpoints > 0:
                checkpoint_count = len([tile for tile in checkpoints_visited])
                draw_text(screen, f"Checkpoints: {checkpoint_count}/{total_checkpoints}", 20, s.checkpoint_colour, 80, 70)

        elif game_state == "GAMEOVER":
            # Display final stats (final_time was captured when transitioning to GAMEOVER)
            checkpoints_passed = len(checkpoints_visited)

            # Draw victory screen with stats
            overlay = pygame.Surface((s.screen_width, s.screen_height))
            overlay.set_alpha(180)
            overlay.fill((0,0,0))
            screen.blit(overlay, (0,0))

            draw_text(screen, "GOAL REACHED!", 60, s.finish_colour, s.screen_width//2, s.screen_height//2 - 80)
            draw_text(screen, f"Total Steps: {total_steps}", 30, s.white, s.screen_width//2, s.screen_height//2 - 10)
            draw_text(screen, f"Time Taken: {final_time:.2f} seconds", 30, s.white, s.screen_width//2, s.screen_height//2 + 30)
            if total_checkpoints > 0:
                draw_text(screen, f"Checkpoints Passed: {checkpoints_passed}/{total_checkpoints}", 25, s.checkpoint_colour, s.screen_width//2, s.screen_height//2 + 70)
            draw_text(screen, "Press SPACE to Replay", 25, s.white, s.screen_width//2, s.screen_height//2 + 120)

        pygame.display.flip()
        clock.tick(s.fps)

    pygame.quit()

if __name__ == "__main__":
    main()