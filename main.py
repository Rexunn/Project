import pygame
import settings as s
from track import Track
from game_engine import PhysicsEngine
from car import CarState
from solver import AStarSolver
from ga import GeneticAlgorithm

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
    track = Track("track2.png") # <-----------
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
    game_state = "MENU" # MENU, LOADING, GENERATING, RUNNING, GAMEOVER
    path = []
    explored_states = []  # All states A* explored (for debug visualization)
    show_ghosts = False  # Toggle for ghost visualization
    path_index = 0

    running = True
    while running:
        # --- EVENT HANDLING ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if event.type == pygame.KEYDOWN:
                if game_state == "MENU" and event.key == pygame.K_SPACE:
                    game_state = "LOADING"
                elif game_state == "MENU" and event.key == pygame.K_n:
                    game_state = "GENERATING"
                elif game_state == "GAMEOVER" and event.key == pygame.K_SPACE:
                    # Reset
                    car = start_state
                    path_index = 0
                    game_state = "RUNNING"
                elif event.key == pygame.K_g:  # Toggle ghost visualization
                    show_ghosts = not show_ghosts
                    print(f"Ghost visualization: {'ON' if show_ghosts else 'OFF'}")

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
            draw_text(screen, "Press N for New GA Track", 30, s.yellow, s.screen_width//2, s.screen_height//2 + 60)

        elif game_state == "LOADING":
            # Draw one frame of "Loading..." before blocking calculation
            draw_text(screen, "Calculating Optimal Path...", 40, s.white, s.screen_width//2, s.screen_height//2)
            pygame.display.flip()
            
            # Run Solver
            solver = AStarSolver(engine)
            path, explored_states = solver.solve(start_state)
            
            if not path:
                print("No Path Found!")
                game_state = "MENU" # Go back if failed
            else:
                game_state = "RUNNING"

        elif game_state == "GENERATING":
            # Draw one frame of "Generating..." before the GA blocks
            draw_text(screen, "Generating Track with GA...", 40, s.yellow, s.screen_width//2, s.screen_height//2)
            pygame.display.flip()

            # Run the Genetic Algorithm
            ga = GeneticAlgorithm(population_size=20, generations=35, mutation_rate=0.05)
            best = ga.run()

            if best.fitness == 0:
                print("GA failed to find a solvable track. Returning to menu.")
                game_state = "MENU"
            else:
                # Build a Track from the GA's best grid
                track = Track.from_grid(best.grid)
                engine = PhysicsEngine(track.grid)

                # Find start position on the new track
                start_x, start_y = best.start_pos
                start_state = CarState(start_x, start_y, 0, 0)
                car = start_state

                # Now solve it with A*
                solver = AStarSolver(engine)
                path, explored_states = solver.solve(start_state)
                path_index = 0

                if not path:
                    print("A* couldn't solve the GA track. Returning to menu.")
                    game_state = "MENU"
                else:
                    game_state = "RUNNING"

        elif game_state == "RUNNING":
            # Auto-replay the path
            if path and path_index < len(path):
                car = path[path_index]
                path_index += 1
                pygame.time.delay(100) # Speed control
            else:
                game_state = "GAMEOVER"

            # Draw Ghost States (if enabled)
            if show_ghosts:
                # Create a set of path positions for quick lookup
                path_positions = {(state.x, state.y) for state in path}

                # Draw all explored states that aren't in the final path
                for state in explored_states:
                    if (state.x, state.y) not in path_positions:
                        px = state.x * track.TILE_SIZE + (track.TILE_SIZE // 2)
                        py = state.y * track.TILE_SIZE + (track.TILE_SIZE // 2)
                        # Semi-transparent red for failed attempts
                        ghost_surface = pygame.Surface((4, 4), pygame.SRCALPHA)
                        pygame.draw.circle(ghost_surface, (255, 0, 0, 80), (2, 2), 2)
                        screen.blit(ghost_surface, (px - 2, py - 2))

            # Draw Path History (Yellow Dots)
            for i in range(path_index):
                step = path[i]
                px = step.x * track.TILE_SIZE + (track.TILE_SIZE // 2)
                py = step.y * track.TILE_SIZE + (track.TILE_SIZE // 2)
                pygame.draw.circle(screen, (255, 255, 0), (px, py), 2)

            # Draw Car
            pixel_x = car.x * track.TILE_SIZE + (track.TILE_SIZE // 2)
            pixel_y = car.y * track.TILE_SIZE + (track.TILE_SIZE // 2)
            pygame.draw.circle(screen, s.white, (pixel_x, pixel_y), track.TILE_SIZE // 2)

            # Debug info
            if show_ghosts:
                draw_text(screen, f"Explored: {len(explored_states)} states", 16, (255, 100, 100), s.screen_width - 150, 20)
                draw_text(screen, "Press G to hide ghosts", 14, (200, 200, 200), s.screen_width - 150, 40)
            else:
                draw_text(screen, "Press G to show ghosts", 14, (200, 200, 200), s.screen_width - 150, 20)

        elif game_state == "GAMEOVER":
            draw_text(screen, "GOAL REACHED!", 50, s.finish_colour, s.screen_width//2, s.screen_height//2)
            draw_text(screen, "Press SPACE to Replay", 30, s.white, s.screen_width//2, s.screen_height//2 + 50)

        pygame.display.flip()
        clock.tick(s.fps)

    pygame.quit()

if __name__ == "__main__":
    main()
