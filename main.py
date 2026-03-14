import pygame
import random
import time
import math
import settings as s
from track import Track
from game_engine import PhysicsEngine
from car import CarState, Racer
from solver import AStarSolver
from ga import GeneticAlgorithm

def draw_text(screen, text, size, color, x, y):
    font = pygame.font.SysFont("arial", size, bold=True)
    surface = font.render(text, True, color)
    rect = surface.get_rect(center=(x, y))
    screen.blit(surface, rect)

# --- CPU AI FUNCTIONS ---

def cpu_easy_move(engine, state):
    """Random valid move. No strategy at all."""
    moves = engine.get_legal_moves(state)
    if not moves:
        return None
    return random.choice(moves)

def cpu_medium_move(engine, state, target):
    """Greedy: pick the legal move closest to the target (Manhattan distance)"""
    moves = engine.get_legal_moves(state)
    if not moves:
        return None
    return min(moves, key=lambda m: abs(m.x - target[0]) + abs(m.y - target[1]))

def sort_checkpoints_by_circuit(clusters, grid):
    """
    Sort checkpoint clusters by angle from the grid center.
    This gives them a natural circuit order (clockwise around the track).
    """
    cx = len(grid[0]) // 2  #grid center x
    cy = len(grid) // 2     #grid center y

    def cluster_angle(cluster):
        # Average position of all tiles in the cluster
        avg_x = sum(x for x, y in cluster) / len(cluster)
        avg_y = sum(y for x, y in cluster) / len(cluster)
        return math.atan2(avg_y - cy, avg_x - cx)

    return sorted(clusters, key=cluster_angle)

def get_cpu_target(racer, checkpoint_clusters, track):
    """Figure out what the CPU should aim for: next sequential checkpoint or finish"""
    next_cp = len(racer.checkpoints_cleared)  #index of next checkpoint to hit

    # Still have checkpoints to clear (in order)
    if next_cp < len(checkpoint_clusters):
        cluster = checkpoint_clusters[next_cp]
        avg_x = sum(x for x, y in cluster) // len(cluster)
        avg_y = sum(y for x, y in cluster) // len(cluster)
        return (avg_x, avg_y)

    # All checkpoints cleared — aim for finish
    for r in range(len(track.grid)):
        for c in range(len(track.grid[0])):
            if track.grid[r][c] == 3:
                return (c, r)

    return (racer.state.x, racer.state.y)  #fallback

def check_racer_progress(racer, track, checkpoint_clusters):
    """Check if a racer hit the NEXT checkpoint in sequence, or the finish line"""
    x, y = racer.state.x, racer.state.y

    # Bounds check
    if y < 0 or y >= len(track.grid) or x < 0 or x >= len(track.grid[0]):
        return

    tile = track.grid[y][x]
    next_cp = len(racer.checkpoints_cleared)  #which checkpoint we need next

    # Checkpoint hit? Only counts if it's the NEXT one in sequence
    if tile == 4 and next_cp < len(checkpoint_clusters):
        target_cluster = checkpoint_clusters[next_cp]
        if (x, y) in target_cluster:
            racer.checkpoints_cleared.add(next_cp)
            print(f"{racer.name} cleared checkpoint {next_cp + 1}/{len(checkpoint_clusters)}")

    # Finish line hit? (only counts if ALL checkpoints cleared in order)
    if tile == 3:
        if len(racer.checkpoints_cleared) >= len(checkpoint_clusters):
            racer.finished = True
            print(f"{racer.name} FINISHED!")

# --- DRAWING HELPERS ---

def draw_legal_moves(screen, moves, selected_ax, selected_ay, current_state, track):
    """Show where each acceleration choice would land the car"""
    for move in moves:
        px = move.x * track.TILE_SIZE + (track.TILE_SIZE // 2)
        py = move.y * track.TILE_SIZE + (track.TILE_SIZE // 2)

        # Figure out what acceleration produced this move
        ax = move.vx - current_state.vx
        ay = move.vy - current_state.vy

        # Highlight the currently selected one
        if ax == selected_ax and ay == selected_ay:
            pygame.draw.circle(screen, s.green, (px, py), 6)
        else:
            # Semi-transparent dot for other options
            dot = pygame.Surface((8, 8), pygame.SRCALPHA)
            pygame.draw.circle(dot, (255, 255, 255, 100), (4, 4), 4)
            screen.blit(dot, (px - 4, py - 4))

def draw_timer_bar(screen, time_remaining, max_time):
    """Draw a countdown bar at the top of the screen"""
    bar_width = 300
    bar_height = 20
    bar_x = s.screen_width // 2 - bar_width // 2
    bar_y = 10

    # Background
    pygame.draw.rect(screen, s.black, (bar_x, bar_y, bar_width, bar_height))

    # Fill (green -> red as time runs out)
    ratio = max(0, time_remaining / max_time)
    fill_width = int(bar_width * ratio)
    color = s.green if ratio > 0.33 else s.red
    pygame.draw.rect(screen, color, (bar_x, bar_y, fill_width, bar_height))

    # Label
    draw_text(screen, f"{time_remaining:.1f}s", 16, s.white, s.screen_width // 2, bar_y + bar_height + 12)

def draw_leaderboard(screen, racers, checkpoint_clusters, current_turn):
    """Draw race progress in the top-right corner"""
    total_cp = len(checkpoint_clusters)
    x = s.screen_width - 180
    y = 10

    draw_text(screen, f"Turn: {current_turn}", 16, s.white, x, y)
    y += 25

    for racer in racers:
        cp_count = len(racer.checkpoints_cleared)
        status = "FINISHED" if racer.finished else ("CRASHED" if racer.crashed else f"{cp_count}/{total_cp} CP")
        draw_text(screen, f"{racer.name}: {status}", 14, racer.color, x, y)
        y += 20

def draw_racers(screen, racers, track):
    """Draw all racer circles on the track"""
    for racer in racers:
        if racer.crashed:
            continue
        px = racer.state.x * track.TILE_SIZE + (track.TILE_SIZE // 2)
        py = racer.state.y * track.TILE_SIZE + (track.TILE_SIZE // 2)
        pygame.draw.circle(screen, racer.color, (px, py), track.TILE_SIZE // 2)
        # Small black outline so overlapping cars are visible
        pygame.draw.circle(screen, s.black, (px, py), track.TILE_SIZE // 2, 1)

# --- MAIN GAME ---

def main():
    pygame.init()
    screen = pygame.display.set_mode((s.screen_width, s.screen_height))
    pygame.display.set_caption("Racetrack AI Prototype")
    clock = pygame.time.Clock()

    # --- LOADING ASSETS ---
    track = Track("track2.png")
    engine = PhysicsEngine(track.grid)

    # Find Start Position
    start_x, start_y = 5, 5
    for r in range(track.rows):
        for c in range(track.cols):
            if track.grid[r][c] == 2:
                start_x, start_y = c, r
                break

    start_state = CarState(start_x, start_y, 0, 0)

    # --- GAME VARIABLES ---
    game_state = "MENU"  # MENU, LOADING, GENERATING, RUNNING, GAMEOVER
    racers = []
    checkpoint_clusters = []
    current_turn = 0
    race_phase = "INPUT"  # INPUT, EXECUTE
    player_ax = 0   #selected acceleration
    player_ay = 0
    turn_start_time = 0
    winner = None

    running = True
    while running:
        dt = clock.tick(s.fps) / 1000.0  #delta time in seconds

        # --- EVENT HANDLING ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                # --- MENU ---
                if game_state == "MENU":
                    if event.key == pygame.K_SPACE:
                        game_state = "LOADING"
                    elif event.key == pygame.K_n:
                        game_state = "GENERATING"

                # --- RUNNING (player input) ---
                elif game_state == "RUNNING" and race_phase == "INPUT":
                    if event.key == pygame.K_UP:
                        player_ay = max(-2, player_ay - 1)
                    elif event.key == pygame.K_DOWN:
                        player_ay = min(2, player_ay + 1)
                    elif event.key == pygame.K_LEFT:
                        player_ax = max(-2, player_ax - 1)
                    elif event.key == pygame.K_RIGHT:
                        player_ax = min(2, player_ax + 1)
                    elif event.key == pygame.K_SPACE:
                        race_phase = "EXECUTE"  #confirm move

                # --- GAMEOVER ---
                elif game_state == "GAMEOVER":
                    if event.key == pygame.K_SPACE:
                        game_state = "MENU"

        # --- LOGIC & DRAWING ---
        screen.fill(s.gray)
        track.draw(screen)

        # ==================== MENU ====================
        if game_state == "MENU":
            overlay = pygame.Surface((s.screen_width, s.screen_height))
            overlay.set_alpha(128)
            overlay.fill((0, 0, 0))
            screen.blit(overlay, (0, 0))

            draw_text(screen, "RACETRACK AI", 60, s.white, s.screen_width // 2, s.screen_height // 2 - 50)
            draw_text(screen, "Press SPACE to Race (Loaded Track)", 30, s.white, s.screen_width // 2, s.screen_height // 2 + 20)
            draw_text(screen, "Press N for New GA Track", 30, s.yellow, s.screen_width // 2, s.screen_height // 2 + 60)

        # ==================== LOADING ====================
        elif game_state == "LOADING":
            draw_text(screen, "Setting up race...", 40, s.white, s.screen_width // 2, s.screen_height // 2)
            pygame.display.flip()

            # --- CREATE RACERS ---
            solver = AStarSolver(engine)
            checkpoint_clusters = solver._get_clusters(4)
            checkpoint_clusters = sort_checkpoints_by_circuit(checkpoint_clusters, track.grid)
            print(f"Checkpoints sorted in circuit order: {len(checkpoint_clusters)} total")

            # Player
            player = Racer(start_state, s.racer_colours["PLAYER"], "PLAYER", "You")
            racers = [player]

            # CPU Easy
            cpu_easy = Racer(start_state, s.racer_colours["CPU_EASY"], "CPU_EASY", "CPU Easy")
            racers.append(cpu_easy)

            # CPU Medium
            cpu_med = Racer(start_state, s.racer_colours["CPU_MEDIUM"], "CPU_MEDIUM", "CPU Med")
            racers.append(cpu_med)

            # CPU Hard (pre-compute optimal path)
            cpu_hard = Racer(start_state, s.racer_colours["CPU_HARD"], "CPU_HARD", "CPU Hard")
            hard_path, _ = solver.solve(start_state)
            if hard_path:
                cpu_hard.precomputed_path = hard_path
            racers.append(cpu_hard)

            print(f"Race ready! {len(racers)} racers, {len(checkpoint_clusters)} checkpoints")

            # Reset race state
            current_turn = 0
            race_phase = "INPUT"
            player_ax = 0
            player_ay = 0
            turn_start_time = time.time()
            winner = None
            game_state = "RUNNING"

        # ==================== GENERATING ====================
        elif game_state == "GENERATING":
            draw_text(screen, "Generating Track with GA...", 40, s.yellow, s.screen_width // 2, s.screen_height // 2)
            pygame.display.flip()

            ga = GeneticAlgorithm(population_size=20, generations=35, mutation_rate=0.3)
            best = ga.run()

            if best.fitness == 0:
                print("GA failed. Returning to menu.")
                game_state = "MENU"
            else:
                # Build track from GA grid
                track = Track.from_grid(best.grid)
                engine = PhysicsEngine(track.grid)

                # Update start position
                start_x, start_y = best.start_pos
                start_state = CarState(start_x, start_y, 0, 0)

                # Go to LOADING to set up the race
                game_state = "LOADING"

        # ==================== RUNNING ====================
        elif game_state == "RUNNING":

            # --- INPUT PHASE: player picks acceleration ---
            if race_phase == "INPUT":
                # Timer
                elapsed = time.time() - turn_start_time
                time_remaining = s.turn_time_limit - elapsed

                # Timer expired — force car to stay in place (velocity reset to 0)
                if time_remaining <= 0:
                    player_racer = racers[0]
                    player_racer.state = CarState(player_racer.state.x, player_racer.state.y, 0, 0)
                    race_phase = "EXECUTE"

                # Draw player's legal moves
                player_racer = racers[0]
                if not player_racer.finished and not player_racer.crashed:
                    legal_moves = engine.get_legal_moves(player_racer.state)
                    draw_legal_moves(screen, legal_moves, player_ax, player_ay, player_racer.state, track)
                    draw_timer_bar(screen, max(0, time_remaining), s.turn_time_limit)

                    # Show selected acceleration
                    draw_text(screen, f"Accel: ({player_ax}, {player_ay})", 18, s.white, s.screen_width // 2, s.screen_height - 30)
                    draw_text(screen, "Arrow Keys to aim, SPACE to confirm", 14, (200, 200, 200), s.screen_width // 2, s.screen_height - 10)
                else:
                    # Player already finished/crashed, skip to execute
                    race_phase = "EXECUTE"

            # --- EXECUTE PHASE: all racers move ---
            if race_phase == "EXECUTE":
                for racer in racers:
                    if racer.finished or racer.crashed:
                        continue

                    new_state = None

                    if racer.type == "PLAYER":
                        # If timer forced a stop, state is already updated — just check progress
                        if racer.state.vx == 0 and racer.state.vy == 0 and player_ax == 0 and player_ay == 0:
                            new_state = racer.state
                        else:
                            # Apply player's chosen acceleration
                            new_vx = racer.state.vx + player_ax
                            new_vy = racer.state.vy + player_ay
                            # Clamp velocity
                            new_vx = max(-5, min(5, new_vx))
                            new_vy = max(-5, min(5, new_vy))
                            new_x = racer.state.x + new_vx
                            new_y = racer.state.y + new_vy

                            # Validate the move — hitting a wall = crash
                            if engine._check_path(racer.state.x, racer.state.y, new_x, new_y) and engine._is_safe(new_x, new_y):
                                new_state = CarState(new_x, new_y, new_vx, new_vy)
                            else:
                                racer.crashed = True
                                print(f"{racer.name} CRASHED into a wall!")
                                continue

                    elif racer.type == "CPU_EASY":
                        new_state = cpu_easy_move(engine, racer.state)

                    elif racer.type == "CPU_MEDIUM":
                        target = get_cpu_target(racer, checkpoint_clusters, track)
                        new_state = cpu_medium_move(engine, racer.state, target)

                    elif racer.type == "CPU_HARD":
                        if racer.path_index < len(racer.precomputed_path):
                            new_state = racer.precomputed_path[racer.path_index]
                            racer.path_index += 1
                        else:
                            new_state = None  #path exhausted

                    # Apply move or crash
                    if new_state is None:
                        racer.crashed = True
                        print(f"{racer.name} CRASHED! No legal moves.")
                    else:
                        racer.state = new_state
                        check_racer_progress(racer, track, checkpoint_clusters)

                # Check for winner
                for racer in racers:
                    if racer.finished and winner is None:
                        winner = racer

                # Check if race is over
                all_done = all(r.finished or r.crashed for r in racers)
                if winner or all_done or current_turn >= 200:
                    game_state = "GAMEOVER"
                else:
                    # Next turn
                    current_turn += 1
                    race_phase = "INPUT"
                    player_ax = 0
                    player_ay = 0
                    turn_start_time = time.time()

            # Draw all racers
            draw_racers(screen, racers, track)

            # Leaderboard
            draw_leaderboard(screen, racers, checkpoint_clusters, current_turn)

        # ==================== GAMEOVER ====================
        elif game_state == "GAMEOVER":
            # Draw racers in final positions
            draw_racers(screen, racers, track)

            overlay = pygame.Surface((s.screen_width, s.screen_height))
            overlay.set_alpha(160)
            overlay.fill((0, 0, 0))
            screen.blit(overlay, (0, 0))

            if winner:
                draw_text(screen, f"{winner.name} WINS!", 60, winner.color, s.screen_width // 2, s.screen_height // 2 - 50)
            else:
                draw_text(screen, "RACE OVER", 60, s.white, s.screen_width // 2, s.screen_height // 2 - 50)

            draw_text(screen, f"Turns: {current_turn}", 30, s.white, s.screen_width // 2, s.screen_height // 2 + 10)
            draw_text(screen, "Press SPACE to return to Menu", 30, s.white, s.screen_width // 2, s.screen_height // 2 + 50)

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
