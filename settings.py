import pygame

# ── Screen ────────────────────────────────────────────────────────────────────
screen_width  = 1000
screen_height = 800

# ── Frames ────────────────────────────────────────────────────────────────────
fps = 30

# ── Colours ───────────────────────────────────────────────────────────────────
white   = (255, 255, 255)
black   = (0,   0,   0)
gray    = (128, 128, 128)
red     = (255, 0,   0)
green   = (0,   255, 0)
blue    = (0,   0,   255)
yellow  = (255, 255, 0)
cyan    = (0,   200, 200)

# Extended palette
dark_bg    = (12,  12,  22)
panel_bg   = (20,  20,  35)
accent     = (100, 180, 255)
ghost_col  = (255, 255, 255, 90)   # RGBA — used with SRCALPHA surfaces

# Game-specific aliases
bg_colour         = white
wall_colour       = black
finish_colour     = green
track_colour      = gray
checkpoint_colour = yellow

# ── Race settings ─────────────────────────────────────────────────────────────
turn_time_limit = 5.0        # seconds per player turn
PLAYER_LIVES    = 3          # lives before LOSE state triggers
MAX_TURNS       = 250        # turn limit before automatic LOSE

# ── Default track ─────────────────────────────────────────────────────────────
DEFAULT_TRACK = "track2.png"

# ── Racer colours ─────────────────────────────────────────────────────────────
racer_colours = {
    "PLAYER":     white,
    "CPU_EASY":   red,
    "CPU_MEDIUM": cyan,
    "CPU_HARD":   yellow,
}

# ── Ghost colours ─────────────────────────────────────────────────────────────
ghost        = (100, 100, 255, 150)
ghost_crash  = (255, 100, 100, 150)
ghost_finish = (100, 255, 100, 150)

# ── AI Preview animation ──────────────────────────────────────────────────────
AI_PREVIEW_NODES_PER_FRAME = 60    # explored nodes revealed per tick
AI_PREVIEW_PATH_PER_FRAME  = 4     # path steps traced per tick after nodes done
AI_PREVIEW_HOLD_SECS       = 1.8   # seconds to hold path display before auto-advance

# ── Loading hints ─────────────────────────────────────────────
LOADING_HINTS = [
    "Tip: Small acceleration changes = smoother cornering.",
    "This Game was made by Tyrese Morgan",
    "Tip: You only have 5 seconds per turn. Use them wisely.",
    "Tip: Hitting a wall costs you a life. 3 deaths and you're done.",
    "Tip: Clear every checkpoint in order before the finish line counts.",
    "Tip: Press T on the pre-race screen to see the A* vs BFS comparison.",
    "Tip: Genetic Algorithms evolve tracks over 35 generations — each run is unique.",
    "Tip: The ghost car shows your best run. Beat it to save a new record.",
    "Tip: Speed 5 is fast, but hard to steer. Build up gradually.",
    "Tip: CPU Medium is greedy — it always heads straight for the next checkpoint.",
    "Tip: A* is guaranteed to find the shortest path. BFS isn't — it explores much more.",
    "Tip: The cyan dots on the track are the A* ghost line. Follow it for a hint.",
]
