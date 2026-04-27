import pygame

# ── Screen ────────────────────────────────────────────────────────────────────
screen_width  = 1200          # total window width (game canvas + sidebar)
screen_height = 800

# ── Sidebar layout ────────────────────────────────────────────────────────────
SIDEBAR_WIDTH   = 200         # pixel width of the right-hand sidebar
GAME_WIDTH      = screen_width - SIDEBAR_WIDTH   # = 1000 — the playable canvas
BORDER_THICK    = 3           # game-canvas border thickness (px)
BORDER_COLOUR   = (70, 70, 110)  # matches FLASH_PANEL_BORDER

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

dark_bg    = (12,  12,  22)
panel_bg   = (20,  20,  35)
accent     = (100, 180, 255)
ghost_col  = (255, 255, 255, 90)   # RGBA — used with SRCALPHA surfaces

bg_colour         = white
wall_colour       = black
finish_colour     = green
track_colour      = gray
checkpoint_colour = yellow

# ── Race settings ─────────────────────────────────────────────────────────────
turn_time_limit = 5.0
PLAYER_LIVES    = 3
MAX_TURNS       = 250
# ── AI Preview (updated for static fade-in) ───────────────────────────────────
AI_PREVIEW_FADE_SECS  = 0.5    
AI_PREVIEW_HOLD_SECS  = 1.8    # Unified to the lower value from your second block
AI_PREVIEW_NODES_PER_FRAME = 60
AI_PREVIEW_PATH_PER_FRAME  = 4
# ── Wrong way detection ───────────────────────────────────────────────────────
WRONG_WAY_DOT_THRESHOLD = -0.3   # dot product below this triggers warning
WRONG_WAY_MIN_SPEED     = 2      # |vx| or |vy| must exceed this to trigger

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



# ── Loading hints ─────────────────────────────────────────────────────────────
LOADING_HINTS = [
    "Tip: Small acceleration changes = smoother cornering.",
    "This game was made by Tyrese Morgan",
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
    "Tip: Watch out for oil spills — they randomise your acceleration for a few turns.",
    "Tip: Potholes cost a life. Memorise where they are each run.",
    "Tip: Rainy weather cuts your max speed and acceleration range in half.",
    "Tip: Snowy conditions mean you can't brake hard — build momentum slowly.",
]

# ── Weather system ──────────────────────────────────────────────────
# Each mode has three physics parameters used by PhysicsEngine.set_weather():
#   accel_limit  – max |acceleration| per axis in get_legal_moves
#   max_speed    – velocity cap per axis
#   brake_limit  – max deceleration against current velocity (Snowy sliding effect)
#                  Sunny/Rainy set this equal to accel_limit (no extra restriction).
#                  Snowy sets it to 1 so the car can't scrub speed quickly.
WEATHER_MODES = ["Sunny", "Rainy", "Snowy"]
DEFAULT_WEATHER = "Sunny"

WEATHER_PHYSICS = {
    "Sunny": {"accel_limit": 2, "max_speed": 5, "brake_limit": 2},
    "Rainy": {"accel_limit": 1, "max_speed": 3, "brake_limit": 1},
    "Snowy": {"accel_limit": 2, "max_speed": 4, "brake_limit": 1},
}

WEATHER_COLOURS = {
    "Sunny": (255, 210,  60),
    "Rainy": ( 80, 140, 220),
    "Snowy": (200, 220, 255),
}

WEATHER_LABELS = {
    "Sunny": "Sunny",
    "Rainy": "Rainy",
    "Snowy": "Snowy",
}

# ── Obstacle system ─────────────────────────────────────────────────
OBSTACLE_COUNT = 5          # obstacles placed per race
OBSTACLE_TYPES = ["OilSpill", "Pothole"]

# OilSpill: randomises player acceleration for this many turns after contact
OIL_SLICK_TURNS = 3

# ── GA generation controls ──────────────────────────────────────────
GA_DEFAULT_WAYPOINTS = 6    # shown on GA_SETUP screen; range 4-10
GA_DEFAULT_SHARPNESS = 1    # index into GA_SHARPNESS_NAMES (0=Gentle, 1=Normal, 2=Sharp)
GA_SHARPNESS_NAMES   = ["Gentle", "Normal", "Sharp"]

# How each preset changes the GA / track shape:
#   carve_radius – Chromosome._carve_circle radius  (large = wide sweeping road)
#   mut_variance – GeneticAlgorithm.mutate() tile-shift range
#   jitter       – per-waypoint random jitter in random_waypoints()
GA_SHARPNESS_PRESETS = {
    "Gentle": {"carve_radius": 3, "mut_variance": 2, "jitter": 2},
    "Normal": {"carve_radius": 2, "mut_variance": 3, "jitter": 4},
    "Sharp":  {"carve_radius": 1, "mut_variance": 5, "jitter": 6},
}

# ── Flash UI Palette ─────────────────────────────────────────────────
FLASH_PANEL_BG     = (8,  8,  18)
FLASH_PANEL_BORDER = (70, 70, 110)
FLASH_GOLD         = (255, 205, 0)
FLASH_TEAL         = (0,  200, 180)

# ── Trail System  ─────────────────────────────────────────────────────
TRAIL_LENGTH    = 9     # how many historic positions to store per racer
TRAIL_MIN_ALPHA = 15    # alpha at the oldest dot
TRAIL_MAX_ALPHA = 145   # alpha at the newest dot (just behind the racer)

# ── GA Generation Flavour Texts ─────────────────────────────────────
GA_LOADING_TEXTS = [
    "Seeding waypoint genome...",
    "Formulating Catmull-Rom splines...",
    "Testing track corners...",
    "Evaluating circuit flow...",
    "Running A* fitness check...",
    "Culling degenerate chromosomes...",
    "Crossing over parent waypoints...",
    "Applying random mutations...",
    "Sorting population by fitness...",
    "Checking corridor widths...",
    "Smoothing spline tangents...",
    "Optimising start/finish placement...",
    "Verifying circuit closure...",
    "Computing curvature scores...",
    "Rewarding direction complexity...",
    "Electing best survivor...",
]