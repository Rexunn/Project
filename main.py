"""
main
-------
Full game entry point. State machine driven by GameStateManager.

State flow:
  BOOT_MENU  -> MAP_SELECT | GA_SETUP | LOADING
  GA_SETUP   -> GENERATING | BOOT_MENU
  GENERATING -> LOADING | BOOT_MENU
  LOADING    -> AI_PREVIEW
  AI_PREVIEW -> PRE_RACE
  PRE_RACE   -> RUNNING
  RUNNING    -> WIN | LOSE
  WIN / LOSE -> PRE_RACE | GENERATING | BOOT_MENU
"""

import math
import os
import random
import time

import pygame

import settings as s
from car import CarState, Racer
from ga import GeneticAlgorithm
from game_engine import PhysicsEngine
from game_state_manager import GameState, GameStateManager
from ghost_recorder import (
    GhostCar, 
    GhostRecorder,
    get_leaderboard, 
    load_ghost, 
    save_ghost, 
    track_id,
)
from obstacles import Obstacle, generate_obstacles          
from solver import AStarSolver
from track import Track
from ui import (
    draw_boot_background,
    draw_ga_setup,                                          
    draw_hint_row,
    draw_leaderboard,
    draw_lives,
    draw_menu_list,
    draw_obstacles,                                         
    draw_overlay,
    draw_panel,
    draw_place_badge,
    draw_pulsing_text,
    draw_speed_gauge,
    draw_text,
    draw_timer_bar,
    draw_weather_badge,                                     
    draw_wrong_way_banner,
    draw_static_path_preview,
    draw_naming_overlay,   
    draw_track_leaderboard,                              
)


# ═══════════════════════════════════════════════════════════════════════════════
# CPU AI helpers
# ═══════════════════════════════════════════════════════════════════════════════

def cpu_easy_move(engine, state, cp_forward=None):
    """
    Random legal move with two layers of filtering:
      1. Momentum bias   — prefer moves that don't reverse current velocity.
      2. Directional bias — if a checkpoint forward vector is supplied, discard
                            moves whose resulting velocity points more than ~107
                            degrees away from the circuit direction.
                            This prevents CPU Easy from completing the race
                            by accidentally driving backwards.

    Parameters
    ----------
    cp_forward : tuple(float, float) | None
        Unit vector pointing from the current checkpoint toward the next one.
        None = no directional filter (e.g. when all CPs are cleared).
    """
    moves = engine.get_legal_moves(state)
    if not moves:
        return None

    # Layer 1: momentum bias (existing logic)
    forward = [m for m in moves if
               (state.vx > 0 and m.vx >= 0) or
               (state.vx < 0 and m.vx <= 0) or
               (state.vy > 0 and m.vy >= 0) or
               (state.vy < 0 and m.vy <= 0)]
    pool = forward if (forward and (state.vx != 0 or state.vy != 0)) else moves

    # Layer 2: directional filter using circuit forward vector
    if cp_forward is not None:
        fvx, fvy = cp_forward
        directional = [
            m for m in pool
            if (m.vx * fvx + m.vy * fvy) > s.WRONG_WAY_DOT_THRESHOLD
        ]
        if directional:
            return random.choice(directional)
        # If the filter removes everything (e.g. car is cornered), fall through
        # to the unfiltered pool so it doesn't get completely stuck.

    return random.choice(pool)


def cpu_medium_move(engine, state, target):
    moves = engine.get_legal_moves(state)
    if not moves:
        return None
    return min(moves, key=lambda m: abs(m.x - target[0]) + abs(m.y - target[1]))


def sort_checkpoints_by_circuit(clusters, grid):
    cx = len(grid[0]) // 2
    cy = len(grid)    // 2
    def angle(cl):
        ax = sum(x for x, _ in cl) / len(cl)
        ay = sum(y for _, y in cl) / len(cl)
        return math.atan2(ay - cy, ax - cx)
    return sorted(clusters, key=angle)


def get_cpu_target(racer, checkpoint_clusters, track):
    nxt = len(racer.checkpoints_cleared)
    if nxt < len(checkpoint_clusters):
        cl = checkpoint_clusters[nxt]
        return (sum(x for x, _ in cl) // len(cl),
                sum(y for _, y in cl) // len(cl))
    for r in range(len(track.grid)):
        for c in range(len(track.grid[0])):
            if track.grid[r][c] == 3:
                return (c, r)
    return (racer.state.x, racer.state.y)


# ═══════════════════════════════════════════════════════════════════════════════
# Race-progress checker  
# ═══════════════════════════════════════════════════════════════════════════════

def check_racer_progress(racer, track, checkpoint_clusters, current_turn):
    x, y = racer.state.x, racer.state.y
    if y < 0 or y >= len(track.grid) or x < 0 or x >= len(track.grid[0]):
        return
    tile = track.grid[y][x]
    nxt  = len(racer.checkpoints_cleared)

    #tick down grace counter each turn
    if racer.grace_turns_remaining > 0:
        racer.grace_turns_remaining -= 1

    if tile >= 4 and nxt < len(checkpoint_clusters):
        if (x, y) in checkpoint_clusters[nxt]:
            racer.checkpoints_cleared.add(nxt)
            racer.last_checkpoint_pos = CarState(x, y, 0, 0) #record exact tile
            print(f"{racer.name} CP {nxt+1}/{len(checkpoint_clusters)}")

    # FIX: skip finish detection during respawn grace window
    if (tile == 3
            and len(racer.checkpoints_cleared) >= len(checkpoint_clusters)
            and racer.grace_turns_remaining == 0):
        racer.laps_completed += 1
        if racer.laps_completed >= racer.total_laps:
            racer.finished = True
            if racer.finish_turn is None:
                racer.finish_turn = current_turn
            print(f"{racer.name} FINISHED (turn {current_turn})")
        else:
            racer.checkpoints_cleared.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# In-race drawing helpers
# ═══════════════════════════════════════════════════════════════════════════════

def draw_legal_moves(screen, moves, sel_ax, sel_ay, current_state, track):
    for move in moves:
        px = move.x * track.TILE_SIZE + track.TILE_SIZE // 2
        py = move.y * track.TILE_SIZE + track.TILE_SIZE // 2
        ax = move.vx - current_state.vx
        ay = move.vy - current_state.vy
        if ax == sel_ax and ay == sel_ay:
            pygame.draw.circle(screen, s.green, (px, py), 6)
        else:
            dot = pygame.Surface((8, 8), pygame.SRCALPHA)
            pygame.draw.circle(dot, (255, 255, 255, 90), (4, 4), 4)
            screen.blit(dot, (px - 4, py - 4))


def draw_racers(screen, racers, track):
    for racer in racers:
        if racer.crashed:
            continue
        px = racer.state.x * track.TILE_SIZE + track.TILE_SIZE // 2
        py = racer.state.y * track.TILE_SIZE + track.TILE_SIZE // 2
        pygame.draw.circle(screen, racer.color, (px, py), track.TILE_SIZE // 2)
        pygame.draw.circle(screen, s.black,     (px, py), track.TILE_SIZE // 2, 1)


def draw_ghost_car(screen, ghost_car: GhostCar, current_turn: int, tile_size: int):
    pos = ghost_car.get_position(current_turn)
    if pos is None:
        return
    gx, gy = pos
    px = gx * tile_size + tile_size // 2
    py = gy * tile_size + tile_size // 2
    surf = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
    pygame.draw.circle(surf, (255, 255, 255, 85),
                       (tile_size // 2, tile_size // 2), tile_size // 2 - 1)
    screen.blit(surf, (gx * tile_size, gy * tile_size))
    font = pygame.font.SysFont("arial", 9, bold=True)
    lbl  = font.render("G", True, (200, 200, 200))
    screen.blit(lbl, (px - lbl.get_width() // 2, py - lbl.get_height() // 2))


def draw_active_checkpoint(screen, checkpoint_clusters, player_racer, tile_size):
    idx = len(player_racer.checkpoints_cleared)
    if idx >= len(checkpoint_clusters):
        return
    cluster = checkpoint_clusters[idx]
    if not cluster:
        return
    pulse = (math.sin(time.time() * 5) + 1) / 2
    alpha = int(70 + 110 * pulse)
    surf  = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)
    surf.fill((255, 165, 0, alpha))
    for cx, cy in cluster:
        screen.blit(surf, (cx * tile_size, cy * tile_size))


def draw_checkpoint_numbers(screen, checkpoint_clusters, tile_size):
    for i, cluster in enumerate(checkpoint_clusters):
        if not cluster:
            continue
        cx = sum(x for x, _ in cluster) // len(cluster)
        cy = sum(y for _, y in cluster) // len(cluster)
        px = cx * tile_size + tile_size // 2
        py = cy * tile_size + tile_size // 2
        pygame.draw.circle(screen, s.black, (px, py), 10)
        draw_text(screen, str(i + 1), 13, s.white, px, py)


def get_player_place(player_racer, racers, checkpoint_clusters) -> int:
    total_cp = len(checkpoint_clusters)
    def score(r):
        if r.crashed:  return (-1, 0, 0)
        if r.finished: return (100, -(r.finish_turn or 9999), 0)
        cp   = len(r.checkpoints_cleared)
        dist = float("inf")
        if cp < total_cp and checkpoint_clusters[cp]:
            cl   = checkpoint_clusters[cp]
            cx_  = sum(tx for tx, _ in cl) / len(cl)
            cy_  = sum(ty for _, ty in cl) / len(cl)
            dist = abs(r.state.x - cx_) + abs(r.state.y - cy_)
        return (1, cp, -dist)
    ranked = sorted(racers, key=score, reverse=True)
    for i, r in enumerate(ranked):
        if r is player_racer:
            return i + 1
    return len(racers)


# ═══════════════════════════════════════════════════════════════════════════════
# Race setup helper
# ═══════════════════════════════════════════════════════════════════════════════

def setup_race(engine, track, start_state, screen):
    hint = random.choice(s.LOADING_HINTS)

    def show(msg):
        screen.fill(s.dark_bg)
        draw_text(screen, "LOADING...", 42, s.yellow,
                  s.screen_width // 2, s.screen_height // 2 - 60)
        draw_text(screen, msg, 22, s.white,
                  s.screen_width // 2, s.screen_height // 2)
        draw_panel(screen, s.screen_width // 2, s.screen_height - 60,
                   700, 44, alpha=160)
        draw_text(screen, hint, 16, (160, 160, 160),
                  s.screen_width // 2, s.screen_height - 60, bold=False)
        pygame.display.flip()
        pygame.event.pump()

    show("Extracting checkpoints...")
    solver = AStarSolver(engine)
    checkpoint_clusters = []
    cp_val = 4
    while True:
        clusters = solver._get_clusters(cp_val)
        if not clusters:
            break
        if cp_val == 4 and len(clusters) > 1:
            checkpoint_clusters = sort_checkpoints_by_circuit(clusters, track.grid)
            break
        else:
            checkpoint_clusters.extend(clusters)
        cp_val += 1
    print(f"Checkpoints: {len(checkpoint_clusters)}")

    show("Setting up racers...")
    player   = Racer(start_state, s.racer_colours["PLAYER"],     "PLAYER",     "You")
    cpu_easy = Racer(start_state, s.racer_colours["CPU_EASY"],   "CPU_EASY",   "CPU Easy")
    cpu_med  = Racer(start_state, s.racer_colours["CPU_MEDIUM"], "CPU_MEDIUM", "CPU Med")
    cpu_hard = Racer(start_state, s.racer_colours["CPU_HARD"],   "CPU_HARD",   "CPU Hard")
    racers   = [player, cpu_easy, cpu_med, cpu_hard]

    show("Computing A* path (this takes a moment)...")
    hard_path, all_explored, astar_time = solver.solve(start_state, checkpoint_clusters)
    if hard_path:
        cpu_hard.precomputed_path = hard_path
        cpu_hard.explored_states  = all_explored
        cpu_hard.solve_time       = astar_time

    show("Running BFS for comparison...")
    _, bfs_explored, bfs_time = solver.solve(
        start_state, checkpoint_clusters, use_bfs=True)

    race_stats = {
        "astar_time":  astar_time,
        "astar_nodes": len(all_explored),
        "bfs_time":    bfs_time,
        "bfs_nodes":   len(bfs_explored),
    }
    show("Done!")
    return racers, checkpoint_clusters, race_stats, all_explored, hard_path


# ═══════════════════════════════════════════════════════════════════════════════
# Racer reset helper 
# ═══════════════════════════════════════════════════════════════════════════════

def reset_racers(racers, start_state):
    for r in racers:
        r.state                 = start_state
        r.finished              = False
        r.crashed               = False
        r.checkpoints_cleared   = set()
        r.laps_completed        = 0
        r.finish_turn           = None
        r.path_index            = 0
        r.ghost_positions       = []
        r.grace_turns_remaining = 0   
        r.last_checkpoint_pos = None
        if r.type == "PLAYER":
            r.lives = s.PLAYER_LIVES
def compute_cp_forward_vectors(checkpoint_clusters: list,
                                finish_coords: list) -> list:
    """
    Pre-compute a unit "forward" direction vector for each checkpoint.

    For checkpoint[i], the forward vector points from the centroid of
    checkpoint[i] toward the centroid of checkpoint[i+1].
    For the final checkpoint, it points toward the finish-line centroid.

    These vectors are used by:
      - The player wrong-way HUD warning (dot product check).
      - CPU Easy directional filter (cpu_easy_move with cp_forward=).

    Returns
    -------
    list of (float, float) — one unit vector per checkpoint, in order.
    """
    vectors = []
    n = len(checkpoint_clusters)

    for i in range(n):
        cl = checkpoint_clusters[i]
        cx1 = sum(x for x, _ in cl) / len(cl)
        cy1 = sum(y for _, y in cl) / len(cl)

        if i + 1 < n:
            nxt  = checkpoint_clusters[i + 1]
            cx2  = sum(x for x, _ in nxt) / len(nxt)
            cy2  = sum(y for _, y in nxt) / len(nxt)
        elif finish_coords:
            cx2 = sum(x for x, _ in finish_coords) / len(finish_coords)
            cy2 = sum(y for _, y in finish_coords) / len(finish_coords)
        else:
            vectors.append((1.0, 0.0))   # fallback: point right
            continue

        dx, dy = cx2 - cx1, cy2 - cy1
        length = max(0.001, math.hypot(dx, dy))
        vectors.append((dx / length, dy / length))

    return vectors

def _compute_wrong_way(player_racer, cp_forward_vectors: list) -> bool:
    """
    Compute whether the PLAYER racer is travelling significantly against
    the intended circuit direction.

    This function must only ever be called for the PLAYER racer.
    The assertion is intentional — it documents the invariant and will
    catch any future refactor that accidentally passes a CPU racer.

    CPU racers are directionally guided through separate mechanisms:
      - CPU_EASY  : the cp_forward parameter in cpu_easy_move() filters
                    candidate moves whose velocity opposes the circuit.
      - CPU_MEDIUM: greedy targeting always points toward the next CP,
                    so it cannot sustain a wrong-way vector by design.
      - CPU_HARD  : follows a pre-computed ordered A* path; wrong-way
                    movement is structurally impossible.

    Parameters
    ----------
    player_racer      : Racer — must have type == "PLAYER"
    cp_forward_vectors: list of (float, float) unit vectors, one per CP

    Returns
    -------
    bool — True if the player is going wrong way this frame.
    """
    assert player_racer.type == "PLAYER", (
        "_compute_wrong_way must only be called for the PLAYER racer. "
        f"Got type={player_racer.type!r}"
    )

    nxt_cp = len(player_racer.checkpoints_cleared)

    # All checkpoints already cleared — player is heading to finish.
    # Any direction is valid at this stage; suppress the warning.
    if nxt_cp >= len(cp_forward_vectors):
        return False

    fvx, fvy = cp_forward_vectors[nxt_cp]

    # Dot product of velocity against the forward circuit vector.
    # Negative = moving against the circuit direction.
    dot = player_racer.state.vx * fvx + player_racer.state.vy * fvy

    # Speed guard: avoid false triggers when the player is barely moving
    # or has just respawned (velocity is (0,0) at start_state).
    spd = max(abs(player_racer.state.vx), abs(player_racer.state.vy))

    return dot < s.WRONG_WAY_DOT_THRESHOLD and spd >= s.WRONG_WAY_MIN_SPEED    


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    pygame.init()
    screen = pygame.display.set_mode((s.screen_width, s.screen_height))
    pygame.display.set_caption("The RaceTrack Game")
    clock  = pygame.time.Clock()

    gsm = GameStateManager(GameState.BOOT_MENU)

    # ── Assets ────────────────────────────────────────────────────────────────
    track:       Track         | None = None
    engine:      PhysicsEngine | None = None
    start_state: CarState             = CarState(5, 5, 0, 0)

    # ── Boot menu ─────────────────────────────────────────────────────────────
    MENU_OPTIONS = ["Default Track", "Saved Maps", "Generate New Map"]
    menu_idx     = 0

    # ── Map select ────────────────────────────────────────────────────────────
    saved_maps: list[str] = []
    map_idx               = 0

    # ── Race data ─────────────────────────────────────────────────────────────
    racers:              list = []
    checkpoint_clusters: list = []
    race_stats:          dict = {}

    # ── AI preview animation (static fade-in) ────────────────────────────────
    preview_nodes:       list          = []     # explored states
    preview_path:        list          = []     # optimal path line to draw
    preview_alpha:       float         = 0.0   
    preview_fade_done:   bool          = False 
    preview_fade_start:  float         = 0.0    # time.time() when fade started
    preview_done_time:   float | None  = None  

    # ── Directional enforcement ───────────────────────────────────────────────
    cp_forward_vectors: list = []    # unit vectors, one per checkpoint in order

    # ── In-race state ─────────────────────────────────────────────────────────
    current_turn:    int   = 0
    race_phase:      str   = "INPUT"
    player_ax:       int   = 0
    player_ay:       int   = 0
    turn_start_time: float = 0.0
    race_start_time: float = 0.0
    show_dev_stats:  bool  = False

    # ── Ghost ─────────────────────────────────────────────────────────────────
    ghost_recorder: GhostRecorder   = GhostRecorder()
    ghost_car:      GhostCar | None = None
    tid:            str             = ""
    new_record:     bool            = False

    # ── Track naming ───────────────────────────────────────────────
    naming_mode:       bool = False   # True while player is typing a track name
    track_name_buffer: str  = ""      # characters typed so far

    # ── Respawn flash ─────────────────────────────────────────────────────────
    respawn_flash_until: float = 0.0

    # ── Weather  ────────────────────────────────────────────────────
    current_weather: str = s.DEFAULT_WEATHER

    # ── Obstacles  ──────────────────────────────────────────────────
    obstacles:       list = []
    oil_slick_turns: int  = 0    # turns the oil-slick randomisation lasts

    # ── GA generation controls  ────────────────────────────────────
    ga_waypoints:     int = s.GA_DEFAULT_WAYPOINTS
    ga_sharpness_idx: int = s.GA_DEFAULT_SHARPNESS

    # ═════════════════════════════════════════════════════════════════════════
    # MAIN LOOP
    # ═════════════════════════════════════════════════════════════════════════
    running = True
    while running:
        dt = clock.tick(s.fps) / 1000.0

        # ── Events ────────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:

                 # ── NAMING MODE — intercepts all keys while active ─────────────
                if naming_mode:
                    if event.key == pygame.K_RETURN:
                        # Confirm: use typed name or fall back to timestamp
                        clean = track_name_buffer.strip().replace(" ", "_")
                        fname = (f"{clean}.json"
                                 if clean
                                 else f"custom_track_{int(time.time())}.json")
                        if track:
                            track.save_to_file(fname)
                            # Refresh the saved-maps list immediately so the
                            # new file appears in MAP_SELECT without a restart.
                            saved_maps = sorted(
                                f for f in os.listdir(".")
                                if f.endswith(".json"))
                        naming_mode       = False
                        track_name_buffer = ""
                    elif event.key == pygame.K_ESCAPE:
                        # Cancel: discard typed name without saving
                        naming_mode       = False
                        track_name_buffer = ""
                    elif event.key == pygame.K_BACKSPACE:
                        track_name_buffer = track_name_buffer[:-1]
                    else:
                        # Accept printable ASCII characters only.
                        # pygame.key.name() returns strings like 'a', '1', '-'.
                        ch = event.unicode
                        if ch and ch.isprintable() and len(track_name_buffer) < 40:
                            track_name_buffer += ch
                    continue 

                # ── BOOT_MENU ──────────────────────────────────────────────────
                if gsm == GameState.BOOT_MENU:
                    if event.key == pygame.K_UP:
                        menu_idx = (menu_idx - 1) % len(MENU_OPTIONS)
                    elif event.key == pygame.K_DOWN:
                        menu_idx = (menu_idx + 1) % len(MENU_OPTIONS)
                    elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        if menu_idx == 0:       # Default Track
                            track  = Track(s.DEFAULT_TRACK)
                            engine = PhysicsEngine(track.grid)
                            start_state = _find_start(track)
                            tid = track_id(track.grid)
                            gsm.transition(GameState.LOADING)
                        elif menu_idx == 1:     # Saved Maps
                            saved_maps = sorted(
                                f for f in os.listdir(".") if f.endswith(".json"))
                            map_idx = 0
                            gsm.transition(GameState.MAP_SELECT)
                        else:                   # Generate → GA_SETUP first
                            gsm.transition(GameState.GA_SETUP)

                # ── MAP_SELECT ─────────────────────────────────────────────────
                elif gsm == GameState.MAP_SELECT:
                    if event.key == pygame.K_UP:
                        map_idx = max(0, map_idx - 1)
                    elif event.key == pygame.K_DOWN:
                        map_idx = min(len(saved_maps) - 1, map_idx + 1)
                    elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        if saved_maps:
                            track  = Track.from_file(saved_maps[map_idx])
                            engine = PhysicsEngine(track.grid)
                            start_state = _find_start(track)
                            tid = track_id(track.grid)
                            gsm.transition(GameState.LOADING)
                    elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                        gsm.transition(GameState.BOOT_MENU)

                # ── GA_SETUP  ────────────────────────────────────────
                elif gsm == GameState.GA_SETUP:
                    if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                        gsm.transition(GameState.GENERATING)
                    elif event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                        gsm.transition(GameState.BOOT_MENU)
                    elif event.key == pygame.K_LEFT:
                        ga_waypoints = max(4, ga_waypoints - 1)
                    elif event.key == pygame.K_RIGHT:
                        ga_waypoints = min(10, ga_waypoints + 1)
                    elif event.key == pygame.K_UP:
                        ga_sharpness_idx = max(0, ga_sharpness_idx - 1)
                    elif event.key == pygame.K_DOWN:
                        ga_sharpness_idx = min(
                            len(s.GA_SHARPNESS_NAMES) - 1, ga_sharpness_idx + 1)

                # ── AI_PREVIEW ─────────────────────────────────────────────────
                elif gsm == GameState.AI_PREVIEW:
                    if event.key == pygame.K_SPACE:
                         # Skip fade: jump to hold phase
                        preview_alpha     = 255.0
                        preview_fade_done = True
                        if preview_done_time is None:
                            preview_done_time = time.time()

                # ── PRE_RACE ───────────────────────────────────────────────────
                elif gsm == GameState.PRE_RACE:
                    if event.key == pygame.K_SPACE:
                        # Apply weather physics before the race starts
                        engine.set_weather(current_weather)
                        turn_start_time = time.time()
                        race_start_time = time.time()
                        gsm.transition(GameState.RUNNING)
                    elif event.key == pygame.K_t:
                        show_dev_stats = not show_dev_stats
                    elif event.key == pygame.K_s and track: #Space/W/T are suppressed till confirm/cancel
                        naming_mode       = True
                        track_name_buffer = ""
                    elif event.key == pygame.K_w:             # Cycle weather
                        idx = s.WEATHER_MODES.index(current_weather)
                        current_weather = s.WEATHER_MODES[(idx + 1) % len(s.WEATHER_MODES)]

                # ── RUNNING ────────────────────────────────────────────────────
                #clamp input to engine.accel_limit so weather matters
                elif gsm == GameState.RUNNING and race_phase == "INPUT":
                    lim = engine.accel_limit if engine else 2
                    if   event.key == pygame.K_UP:    player_ay = max(-lim, player_ay - 1)
                    elif event.key == pygame.K_DOWN:  player_ay = min( lim, player_ay + 1)
                    elif event.key == pygame.K_LEFT:  player_ax = max(-lim, player_ax - 1)
                    elif event.key == pygame.K_RIGHT: player_ax = min( lim, player_ax + 1)
                    elif event.key == pygame.K_SPACE: race_phase = "EXECUTE"

                # ── WIN / LOSE ─────────────────────────────────────────────────
                elif gsm.is_in(GameState.WIN, GameState.LOSE):
                    if event.key == pygame.K_r:
                        reset_racers(racers, start_state)
                        ghost_recorder.reset()
                        ghost_car        = _load_ghost_car(tid)
                        obstacles        = generate_obstacles(track.grid)  
                        oil_slick_turns  = 0                               
                        current_turn     = 0
                        race_phase       = "INPUT"
                        player_ax        = 0
                        player_ay        = 0
                        new_record       = False
                        show_dev_stats   = False
                        gsm.transition(GameState.PRE_RACE)
                    elif event.key == pygame.K_g:
                        gsm.transition(GameState.GENERATING)
                    elif event.key == pygame.K_m:
                        gsm.transition(GameState.BOOT_MENU)

        # ── Background ────────────────────────────────────────────────────────
        if track:
            screen.fill(s.gray)
            track.draw(screen)
        else:
            draw_boot_background(screen)

        # ═════════════════════════════════════════════════════════════════════
        # BOOT_MENU
        # ═════════════════════════════════════════════════════════════════════
        if gsm == GameState.BOOT_MENU:
            draw_overlay(screen, alpha=170, color=(5, 5, 15))
            draw_text(screen, "THE RACETRACK GAME", 58, s.white,
                      s.screen_width // 2, 160)
            draw_text(screen, "A  I   R A C I N G", 22, s.accent,
                      s.screen_width // 2, 210, bold=False)
            pygame.draw.line(screen, (60, 60, 80),
                             (200, 250), (s.screen_width - 200, 250), 1)
            draw_menu_list(screen, MENU_OPTIONS, menu_idx,
                           s.screen_width // 2, 310)
            draw_text(screen, "Up/Dn  Navigate    SPACE  Select",
                      16, (130, 130, 150),
                      s.screen_width // 2, s.screen_height - 40, bold=False)

        # ═════════════════════════════════════════════════════════════════════
        # MAP_SELECT
        # ═════════════════════════════════════════════════════════════════════
        elif gsm == GameState.MAP_SELECT:
            draw_overlay(screen, alpha=180, color=(5, 5, 15))
            draw_text(screen, "SELECT A SAVED TRACK", 40, s.yellow,
                      s.screen_width // 2, 80)
            if saved_maps:
                vis   = 8
                start = max(0, min(map_idx - vis // 2, len(saved_maps) - vis))
                shown = saved_maps[start: start + vis]
                draw_menu_list(screen, shown, map_idx - start,
                               s.screen_width // 2, 160, item_height=48)
                draw_text(screen, f"{map_idx + 1} / {len(saved_maps)}",
                          16, (130, 130, 150),
                          s.screen_width // 2, s.screen_height - 70, bold=False)
            else:
                draw_text(screen, "No saved .json tracks found in this folder.",
                          24, s.red, s.screen_width // 2, s.screen_height // 2)
            draw_text(screen, "Up/Dn  Navigate    SPACE  Load    ESC  Back",
                      16, (130, 130, 150),
                      s.screen_width // 2, s.screen_height - 40, bold=False)

        # ═════════════════════════════════════════════════════════════════════
        # GA_SETUP 
        # ═════════════════════════════════════════════════════════════════════
        elif gsm == GameState.GA_SETUP:
            draw_overlay(screen, alpha=180, color=(5, 5, 15))
            draw_ga_setup(screen, ga_waypoints, ga_sharpness_idx)

        # ═════════════════════════════════════════════════════════════════════
        # GENERATING 
        # ═════════════════════════════════════════════════════════════════════
        elif gsm == GameState.GENERATING:
            hint_gen = random.choice(s.LOADING_HINTS)

            def draw_ga_progress(cur_gen, max_gens, history):
                pygame.event.pump()
                screen.fill(s.dark_bg)
                draw_text(screen, "EVOLVING TRACK LAYOUT",
                          40, s.yellow, s.screen_width // 2, 80)
                draw_text(screen, f"Generation  {cur_gen} / {max_gens}",
                          28, s.white, s.screen_width // 2, 130)
                if history:
                    gx, gy, gw, gh = 180, 580, 640, 300
                    pygame.draw.rect(screen, (20, 20, 30), (gx, gy - gh, gw, gh))
                    pygame.draw.rect(screen, (50, 50, 70), (gx, gy - gh, gw, gh), 1)
                    max_fit = max(max(history), 1)
                    pts = [(gx + int(i / max(1, len(history) - 1) * gw),
                            gy - int(f / max_fit * gh))
                           for i, f in enumerate(history)]
                    if len(pts) > 1:
                        pygame.draw.lines(screen, s.green, False, pts, 2)
                    for p in pts:
                        pygame.draw.circle(screen, s.cyan, p, 4)
                    draw_text(screen, f"Best fitness: {history[-1]:.0f}",
                              18, s.white, gx + gw // 2, gy - gh - 18)
                draw_panel(screen, s.screen_width // 2, s.screen_height - 50,
                           700, 40, alpha=160)
                draw_text(screen, hint_gen, 15, (140, 140, 160),
                          s.screen_width // 2, s.screen_height - 50, bold=False)
                pygame.display.flip()

            # pass UI-selected parameters to the GA
            ga = GeneticAlgorithm(
                population_size=20,
                generations=35,
                mutation_rate=0.3,
                num_waypoints=ga_waypoints,
                sharpness=s.GA_SHARPNESS_NAMES[ga_sharpness_idx],
            )
            best = ga.run(update_callback=draw_ga_progress)

            if best.fitness == 0:
                print("GA failed. Returning to menu.")
                gsm.transition(GameState.BOOT_MENU)
            else:
                track  = Track.from_grid(best.grid)
                engine = PhysicsEngine(track.grid)
                start_state = CarState(*best.start_pos, 0, 0)
                tid    = track_id(track.grid)
                gsm.transition(GameState.LOADING)

        # ═════════════════════════════════════════════════════════════════════# ═════════════════════════════════════════════════════════════════════
        # LOADING 
        # ═════════════════════════════════════════════════════════════════════
        elif gsm == GameState.LOADING:
            (racers,
            checkpoint_clusters,
            race_stats,
            preview_nodes,
            preview_path) = setup_race(engine, track, start_state, screen)

            finish_coords = [
                (x, y)
                for y in range(len(track.grid))
                for x in range(len(track.grid[0]))
                if track.grid[y][x] == 3
            ]
            cp_forward_vectors = compute_cp_forward_vectors(
                checkpoint_clusters, finish_coords)

            # ── AI preview: reset fade state ──────────────────────────────────
            preview_alpha      = 0.0
            preview_fade_done  = False
            preview_fade_start = time.time()   # fade begins on first AI_PREVIEW frame
            preview_done_time  = None


            #Ghost
            ghost_recorder.reset()
            ghost_car = _load_ghost_car(tid)

            # Obstacles
            obstacles       = generate_obstacles(track.grid)
            oil_slick_turns = 0

            current_turn   = 0
            race_phase     = "INPUT"
            player_ax      = 0
            player_ay      = 0
            new_record     = False
            show_dev_stats = False

            gsm.transition(GameState.AI_PREVIEW)

        # ═════════════════════════════════════════════════════════════════════
        # AI_PREVIEW
        # ═════════════════════════════════════════════════════════════════════
        elif gsm == GameState.AI_PREVIEW:

            # ── Fade-in logic ─────────────────────────────────────────────────
            if not preview_fade_done:
                elapsed      = time.time() - preview_fade_start
                preview_alpha = min(255.0, (elapsed / s.AI_PREVIEW_FADE_SECS) * 255.0)
                if preview_alpha >= 255.0:
                    preview_fade_done = True
                    preview_done_time = time.time()
            else:
                # Hold phase: auto-advance after hold duration
                if (preview_done_time and
                        time.time() - preview_done_time > s.AI_PREVIEW_HOLD_SECS):
                    gsm.transition(GameState.PRE_RACE)

            # ── Draw static path over track ───────────────────────────────────
            if preview_path and track:
                draw_static_path_preview(
                    screen, preview_path, track, int(preview_alpha))

            # ── UI overlay ────────────────────────────────────────────────────
            draw_overlay(screen, alpha=55)

            draw_text(screen, "A*  OPTIMAL  PATH",
                      30, s.yellow, s.screen_width // 2, 30)

            # Stats line (always visible once path is drawn)
            if preview_alpha > 60:
                draw_text(screen,
                          f"{len(preview_path)} steps  ·  "
                          f"{len(preview_nodes)} nodes explored  ·  "
                          f"{race_stats.get('astar_time', 0):.3f}s",
                          16, s.white,
                          s.screen_width // 2, 68, bold=False)

            if preview_fade_done:
                draw_pulsing_text(screen, "Press SPACE to continue",
                                  22, s.white,
                                  s.screen_width // 2, s.screen_height - 40)

            draw_text(screen, "SPACE  Skip / Advance",
                      13, (90, 90, 100),
                      s.screen_width - 100, s.screen_height - 18, bold=False)

        # ═════════════════════════════════════════════════════════════════════
        # PRE_RACE 
        # ═════════════════════════════════════════════════════════════════════
        elif gsm == GameState.PRE_RACE:
            draw_overlay(screen, alpha=190, color=(0, 0, 10))

            if not show_dev_stats:
                draw_text(screen, "HOW TO PLAY", 46, s.yellow,
                        s.screen_width // 2, s.screen_height // 2 - 140)
                draw_hint_row(screen, "Up/Dn/Lt/Rt", "Aim your acceleration",
                            s.screen_width // 2, s.screen_height // 2 - 72)
                draw_hint_row(screen, "SPACE", "Confirm your move",
                            s.screen_width // 2, s.screen_height // 2 - 34)
                draw_text(screen,
                        "You have 5 seconds per turn — don't let the timer run out!",
                        20, s.red, s.screen_width // 2,
                        s.screen_height // 2 + 6, bold=False)
                draw_text(screen,
                        f"Lives: {s.PLAYER_LIVES}  ·  Hitting a wall costs a life",
                        18, (200, 200, 200), s.screen_width // 2,
                        s.screen_height // 2 + 38, bold=False)
                if ghost_car:
                    draw_text(screen,
                            f"Ghost best: {ghost_car.best_turns} turns — beat it!",
                            18, (160, 220, 160), s.screen_width // 2,
                            s.screen_height // 2 + 66, bold=False)

                # Weather selector
                wcol  = s.WEATHER_COLOURS.get(current_weather, s.white)
                wlbl  = s.WEATHER_LABELS.get(current_weather, current_weather)
                draw_text(screen,
                        f"Weather: {wlbl}   [W to change]",
                        18, wcol, s.screen_width // 2,
                        s.screen_height // 2 + 98, bold=False)

            else:
                draw_text(screen, "ALGORITHM COMPARISON", 38, s.yellow,
                        s.screen_width // 2, s.screen_height // 2 - 80)
                draw_text(screen,
                        f"A*:   {race_stats['astar_time']:.3f}s  |  "
                        f"{race_stats['astar_nodes']} nodes explored",
                        24, s.green, s.screen_width // 2,
                        s.screen_height // 2 - 20)
                draw_text(screen,
                        f"BFS:  {race_stats['bfs_time']:.3f}s  |  "
                        f"{race_stats['bfs_nodes']} nodes explored",
                        24, s.red, s.screen_width // 2,
                        s.screen_height // 2 + 20)
                ratio = race_stats["bfs_nodes"] / max(1, race_stats["astar_nodes"])
                draw_text(screen,
                        f"A* explored {ratio:.1f}x fewer nodes than BFS",
                        18, (180, 180, 180), s.screen_width // 2,
                        s.screen_height // 2 + 58, bold=False)

            pygame.draw.line(screen, (50, 50, 70),
                            (150, s.screen_height // 2 + 124),
                            (s.screen_width - 150, s.screen_height // 2 + 124), 1)
            draw_pulsing_text(screen, "PRESS  SPACE  TO  RACE", 30, s.green,
                            s.screen_width // 2, s.screen_height // 2 + 155)
            draw_text(screen, "T  Toggle AI Stats    S  Save&Name Track    W  Change Weather",
                    15, (100, 100, 120),
                    s.screen_width // 2, s.screen_height - 30, bold=False)
            if naming_mode:
                draw_naming_overlay(screen, track_name_buffer)
        # ═════════════════════════════════════════════════════════════════════
        # RUNNING  (Commits 1, 4, 6)
        # ═════════════════════════════════════════════════════════════════════
        elif gsm == GameState.RUNNING:
            player_racer = racers[0]

            # ── INPUT phase ───────────────────────────────────────────────────
            if race_phase == "INPUT":
                elapsed        = time.time() - turn_start_time
                time_remaining = s.turn_time_limit - elapsed

                if time_remaining <= 0:
                    player_ax  = 0
                    player_ay  = 0
                    race_phase = "EXECUTE"
                elif not player_racer.finished and not player_racer.crashed:

                    # ── Wrong-way detection (PLAYER only) ────────────────────
                    # CPU racers are directionally guided through their own
                    # mechanisms — see _compute_wrong_way() docstring for the
                    # full justification of why this never runs for CPUs.
                    player_racer.wrong_way = _compute_wrong_way(
                        player_racer, cp_forward_vectors)

                    legal = engine.get_legal_moves(player_racer.state)
                    draw_legal_moves(screen, legal, player_ax, player_ay,
                                    player_racer.state, track)
                    draw_timer_bar(screen, time_remaining, s.turn_time_limit)
                    draw_text(screen, f"({player_ax:+d}, {player_ay:+d})",
                            16, s.white, s.screen_width // 2,
                            s.screen_height - 22)

                    # Oil-slick warning overlay
                    if oil_slick_turns > 0:
                        draw_pulsing_text(screen,
                                        f"OIL SLICK  ({oil_slick_turns} turns left)",
                                        22, (220, 140, 30),
                                        s.screen_width // 2,
                                        s.screen_height // 2 - 30,
                                        frequency=4.0)
                else:
                    race_phase = "EXECUTE"

            # ── EXECUTE phase ─────────────────────────────────────────────────
            if race_phase == "EXECUTE":

                # Apply oil-slick acceleration override before any move
                if oil_slick_turns > 0:
                    player_ax = random.randint(-engine.accel_limit, engine.accel_limit)
                    player_ay = random.randint(-engine.accel_limit, engine.accel_limit)
                    oil_slick_turns -= 1

                for racer in racers:
                    if racer.finished or racer.crashed:
                        continue

                    new_state = None

                    if racer.type == "PLAYER":
                        # Clamp acceleration to current weather limits
                        eff_ax = max(-engine.accel_limit,
                                    min(engine.accel_limit, player_ax))
                        eff_ay = max(-engine.accel_limit,
                                    min(engine.accel_limit, player_ay))

                        # snowy weather reduces effective acceleration and braking, making it harder to change speed or stop
                        if engine.weather == "Snowy":
                            if racer.state.vx != 0 and eff_ax * racer.state.vx < 0:
                                eff_ax = max(-engine.brake_limit,
                                            min(engine.brake_limit, eff_ax))
                            if racer.state.vy != 0 and eff_ay * racer.state.vy < 0:
                                eff_ay = max(-engine.brake_limit,
                                            min(engine.brake_limit, eff_ay))

                        new_vx = max(-engine.max_speed,
                                    min(engine.max_speed, racer.state.vx + eff_ax))
                        new_vy = max(-engine.max_speed,
                                    min(engine.max_speed, racer.state.vy + eff_ay))
                        new_x  = racer.state.x + new_vx
                        new_y  = racer.state.y + new_vy

                        if (engine._check_path(racer.state.x, racer.state.y,
                                            new_x, new_y)
                                and engine._is_safe(new_x, new_y)):
                            new_state = CarState(new_x, new_y, new_vx, new_vy)
                        else:
                            # Preserve lap data on respawn
                            racer.lives -= 1
                            print(f"{racer.name} crashed! {racer.lives} lives left.")
                            if racer.lives <= 0:
                                racer.crashed = True
                            else:
                                saved_laps              = racer.laps_completed
                                saved_cps               = set(racer.checkpoints_cleared)
                                respawn_state = (
                                    racer.last_checkpoint_pos
                                    if racer.last_checkpoint_pos is not None
                                    else start_state
                                )
                                racer.state             = start_state
                                racer.laps_completed    = saved_laps
                                racer.checkpoints_cleared = saved_cps
                                racer.grace_turns_remaining = 3
                                respawn_flash_until = time.time() + 0.6
                                player_ax = 0
                                player_ay = 0
                            continue

                    elif racer.type == "CPU_EASY":
                        nxt_cp = len(racer.checkpoints_cleared)
                        fwd    = (cp_forward_vectors[nxt_cp]
                                  if nxt_cp < len(cp_forward_vectors) else None)
                        new_state = cpu_easy_move(engine, racer.state,
                                                   cp_forward=fwd)
                    elif racer.type == "CPU_MEDIUM":
                        target    = get_cpu_target(racer, checkpoint_clusters, track)
                        new_state = cpu_medium_move(engine, racer.state, target)
                    elif racer.type == "CPU_HARD":
                        if racer.path_index < len(racer.precomputed_path):
                            new_state        = racer.precomputed_path[racer.path_index]
                            racer.path_index += 1

                    if new_state is None:
                        racer.crashed = True
                        print(f"{racer.name} out of moves — crashed.")
                    else:
                        racer.state = new_state
                        check_racer_progress(racer, track,
                                            checkpoint_clusters, current_turn)

                        #obstacle check (player only)
                        if racer.type == "PLAYER":
                            for obs in obstacles:
                                if (obs.active
                                        and abs(obs.x - new_state.x) <= 1
                                        and abs(obs.y - new_state.y) <= 1):
                                    if obs.type == "OilSpill":
                                        oil_slick_turns = s.OIL_SLICK_TURNS
                                        print("[OIL] Player hit an oil spill!")
                                    elif obs.type == "Pothole":
                                        obs.active = False
                                        racer.lives -= 1
                                        print(f"[POTHOLE] Racer hit a pothole! "
                                            f"{racer.lives} lives left.")
                                        if racer.lives <= 0:
                                            racer.crashed = True
                                        else:
                                            saved_laps  = racer.laps_completed
                                            saved_cps   = set(racer.checkpoints_cleared)
                                            racer.state = start_state
                                            racer.laps_completed      = saved_laps
                                            racer.checkpoints_cleared = saved_cps
                                            racer.grace_turns_remaining = 3
                                            respawn_flash_until = time.time() + 0.6
                                            player_ax = 0
                                            player_ay = 0

                # Ghost recording
                if not player_racer.crashed:
                    ghost_recorder.record(player_racer.state.x,
                                        player_racer.state.y)

                # End conditions
                if player_racer.finished:
                    new_record = save_ghost(tid, ghost_recorder.positions,
                                            current_turn, racer_name="You")
                    gsm.transition(GameState.WIN)
                elif player_racer.crashed or current_turn >= s.MAX_TURNS:
                    gsm.transition(GameState.LOSE)
                else:
                    current_turn   += 1
                    race_phase      = "INPUT"
                    player_ax       = 0
                    player_ay       = 0
                    turn_start_time = time.time()
                    player_racer.wrong_way = False  # reset wrong-way status each turn

            # ── Drawing ───────────────────────────────────────────────────────

            # Ghost car
            if ghost_car and track:
                draw_ghost_car(screen, ghost_car, current_turn, track.TILE_SIZE)

            # CPU Hard ghost line
            for r in racers:
                if r.type == "CPU_HARD" and r.precomputed_path:
                    for st in r.precomputed_path:
                        px = st.x * track.TILE_SIZE + track.TILE_SIZE // 2
                        py = st.y * track.TILE_SIZE + track.TILE_SIZE // 2
                        pygame.draw.circle(screen, (0, 160, 160), (px, py), 2)

            draw_active_checkpoint(screen, checkpoint_clusters,
                                player_racer, track.TILE_SIZE)
            draw_checkpoint_numbers(screen, checkpoint_clusters, track.TILE_SIZE)

            #Draw obstacles beneath racers
            draw_obstacles(screen, obstacles, track.TILE_SIZE)

            draw_racers(screen, racers, track)

            # Wrong-way banner (player only, purely cosmetic)
            if player_racer.wrong_way:
                draw_wrong_way_banner(screen)

            # Respawn flash
            if time.time() < respawn_flash_until:
                flash = pygame.Surface((s.screen_width, s.screen_height),
                                    pygame.SRCALPHA)
                flash.fill((255, 50, 50, 80))
                screen.blit(flash, (0, 0))
                draw_text(screen,
                        f"CRASHED!  {player_racer.lives} lives left",
                        36, s.red,
                        s.screen_width // 2, s.screen_height // 2)

            # ── HUD ───────────────────────────────────────────────────────────

            # Top-left: position badge
            place = get_player_place(player_racer, racers, checkpoint_clusters)
            draw_place_badge(screen, place, 45, 30)

            # Top-right: speed + lives
            draw_panel(screen, s.screen_width - 90, 30, 160, 56, alpha=160)
            draw_speed_gauge(screen,
                            player_racer.state.vx, player_racer.state.vy,
                            s.screen_width - 95, 22)
            draw_lives(screen, player_racer.lives, player_racer.max_lives,
                    s.screen_width - 90, 46)

            # Weather indicator below the HUD panel
            wcol = s.WEATHER_COLOURS.get(current_weather, s.white)
            draw_text(screen,
                    s.WEATHER_LABELS.get(current_weather, current_weather),
                    13, wcol, s.screen_width - 90, 66, bold=False)

            # Right side: leaderboard
            draw_leaderboard(screen, racers, checkpoint_clusters, current_turn)

        # ═════════════════════════════════════════════════════════════════════
        # WIN
        # ═════════════════════════════════════════════════════════════════════
        elif gsm == GameState.WIN:
            draw_overlay(screen, alpha=175, color=(0, 10, 0))
            draw_text(screen, "YOU  WIN",
                    60, s.yellow, s.screen_width // 2,
                    s.screen_height // 2 - 110)
            mins = current_turn // 60
            secs = current_turn % 60
            draw_text(screen,
                    f"Finished in  {current_turn} turns  ({mins}m {secs}s equiv.)",
                    26, s.white,
                    s.screen_width // 2, s.screen_height // 2 - 45)
            if new_record:
                draw_pulsing_text(screen, "NEW  GHOST  RECORD",
                                28, s.green,
                                s.screen_width // 2, s.screen_height // 2)
            elif ghost_car:
                diff = current_turn - ghost_car.best_turns
                col  = s.green if diff <= 0 else s.red
                sign = "+" if diff > 0 else ""
                draw_text(screen,
                        f"Ghost: {ghost_car.best_turns} turns  ({sign}{diff})",
                        22, col, s.screen_width // 2, s.screen_height // 2)
            board = get_leaderboard(tid)
            if board:
                draw_track_leaderboard(
                    screen, board,
                    cx=s.screen_width // 2,
                    cy=s.screen_height // 2 + 46)
            pygame.draw.line(screen, (40, 80, 40),
                            (150, s.screen_height // 2 + 30),
                            (s.screen_width - 150, s.screen_height // 2 + 30), 1)
            draw_hint_row(screen, "R", "Race again (same track)",
                        s.screen_width // 2, s.screen_height // 2 + 60,
                        highlight=True)
            draw_hint_row(screen, "G", "Generate a new track",
                        s.screen_width // 2, s.screen_height // 2 + 95)
            draw_hint_row(screen, "M", "Main menu",
                        s.screen_width // 2, s.screen_height // 2 + 130)

        # ═════════════════════════════════════════════════════════════════════
        # LOSE
        # ═════════════════════════════════════════════════════════════════════
        elif gsm == GameState.LOSE:
            draw_overlay(screen, alpha=185, color=(15, 0, 0))
            draw_text(screen, "GAME  OVER",
                    66, s.red, s.screen_width // 2,
                    s.screen_height // 2 - 110)
            reason = ("Out of lives!" if racers and racers[0].crashed
                    else f"Turn limit reached ({s.MAX_TURNS} turns).")
            draw_text(screen, reason, 26, s.white,
                    s.screen_width // 2, s.screen_height // 2 - 45)
            draw_text(screen, f"You made it to turn {current_turn}.",
                    20, (180, 180, 180),
                    s.screen_width // 2, s.screen_height // 2 - 10,
                    bold=False)
            pygame.draw.line(screen, (80, 20, 20),
                            (150, s.screen_height // 2 + 25),
                            (s.screen_width - 150, s.screen_height // 2 + 25), 1)
            draw_hint_row(screen, "R", "Try again (same track)",
                        s.screen_width // 2, s.screen_height // 2 + 60,
                        highlight=True)
            draw_hint_row(screen, "G", "Generate a new track",
                        s.screen_width // 2, s.screen_height // 2 + 95)
            draw_hint_row(screen, "M", "Main menu",
                        s.screen_width // 2, s.screen_height // 2 + 130)

        pygame.display.flip()

    pygame.quit()


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level helpers (called from main but kept outside to reduce nesting)
# ═══════════════════════════════════════════════════════════════════════════════

def _find_start(track: Track) -> CarState:
    """Scan the grid for tile value 2 (start) and return a CarState there."""
    for r in range(track.rows):
        for c in range(track.cols):
            if track.grid[r][c] == 2:
                return CarState(c, r, 0, 0)
    return CarState(5, 5, 0, 0)   # fallback


def _load_ghost_car(tid: str) -> GhostCar | None:
    """Load and return a GhostCar for the given track ID, or None."""
    if not tid:
        return None
    data = load_ghost(tid)
    return GhostCar(data) if data else None


if __name__ == "__main__":
    main()
