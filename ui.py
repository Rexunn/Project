"""
ui.py
-----------------
All reusable drawing utilities live here.
Import this everywhere instead of duplicating draw_text/overlays/HUD pieces.
Font objects are cached so we never create them mid-frame.
"""

import math
import time

import pygame
import settings as s


# ── Font cache ────────────────────────────────────────────────────────────────

_font_cache: dict[tuple, pygame.font.Font] = {}


def get_font(size: int, bold: bool = True) -> pygame.font.Font:
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.SysFont("arial", size, bold=bold)
    return _font_cache[key]


# ── Core text / panel helpers ─────────────────────────────────────────────────

def draw_text(screen: pygame.Surface, text: str, size: int, color,
              x: int, y: int, bold: bool = True,
              alpha: int = 255) -> pygame.Rect:
    """Render centred text. Returns the bounding rect."""
    surf = get_font(size, bold).render(text, True, color)
    if alpha < 255:
        surf.set_alpha(alpha)
    rect = surf.get_rect(center=(x, y))
    screen.blit(surf, rect)
    return rect


def draw_panel(screen: pygame.Surface, cx: int, cy: int,
               w: int, h: int,
               color=(0, 0, 0), alpha: int = 180) -> None:
    """Semi-transparent filled rectangle, centred on (cx, cy)."""
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill((*color[:3], alpha))
    screen.blit(surf, (cx - w // 2, cy - h // 2))


def draw_overlay(screen: pygame.Surface,
                 alpha: int = 160,
                 color=(0, 0, 0)) -> None:
    """Full-screen translucent overlay."""
    surf = pygame.Surface((s.screen_width, s.screen_height))
    surf.set_alpha(alpha)
    surf.fill(color)
    screen.blit(surf, (0, 0))


# ── Animated text ─────────────────────────────────────────────────────────────

def draw_pulsing_text(screen: pygame.Surface, text: str, size: int, color,
                      x: int, y: int,
                      frequency: float = 2.0,
                      min_alpha: int = 80) -> None:
    """Text whose alpha pulses using a sine wave — used for 'Press SPACE'."""
    pulse = (math.sin(time.time() * frequency * math.pi) + 1) / 2
    alpha = int(min_alpha + (255 - min_alpha) * pulse)
    draw_text(screen, text, size, color, x, y, alpha=alpha)


# ── Key-hint row ──────────────────────────────────────────────────────────────

def draw_hint_row(screen: pygame.Surface, key: str, description: str,
                  x: int, y: int, highlight: bool = False) -> None:
    """Render  [KEY]  description  centred on (x, y)."""
    key_color  = s.yellow if highlight else s.cyan
    desc_color = s.white  if highlight else (190, 190, 190)
    key_surf  = get_font(18).render(f"[{key}]", True, key_color)
    desc_surf = get_font(18, bold=False).render(f"  {description}", True, desc_color)
    total_w   = key_surf.get_width() + desc_surf.get_width()
    bx = x - total_w // 2
    by = y - key_surf.get_height() // 2
    screen.blit(key_surf,  (bx, by))
    screen.blit(desc_surf, (bx + key_surf.get_width(), by))


# ── HUD: lives ────────────────────────────────────────────────────────────────

def draw_lives(screen: pygame.Surface,
               lives: int, max_lives: int,
               x: int, y: int) -> None:
    """Row of coloured circles showing lives remaining."""
    radius = 8
    gap    = 22
    total_w = max_lives * gap
    sx = x - total_w // 2
    for i in range(max_lives):
        cx     = sx + i * gap + radius
        filled = i < lives
        color  = s.red if filled else (50, 50, 50)
        pygame.draw.circle(screen, color, (cx, y), radius)
        pygame.draw.circle(screen, (160, 160, 160), (cx, y), radius, 1)


# ── HUD: speed gauge ─────────────────────────────────────────────────────────

def draw_speed_gauge(screen: pygame.Surface,
                     vx: int, vy: int,
                     x: int, y: int) -> None:
    """Flash-style segmented speed bar — larger, more contrast."""
    speed = max(abs(vx), abs(vy))
    draw_text(screen, "SPD", 11, (160, 160, 185), x - 34, y, bold=False)
    seg_w, seg_h, gap = 12, 16, 3
    for i in range(1, 6):
        bx = x - 6 + (i - 1) * (seg_w + gap)
        filled = (i <= speed)
        if not filled:
            bg = (30, 30, 48)
            pygame.draw.rect(screen, bg, (bx, y - seg_h // 2, seg_w, seg_h))
            pygame.draw.rect(screen, (50, 50, 70),
                             (bx, y - seg_h // 2, seg_w, seg_h), 1)
        else:
            if   i <= 2: col = (50, 210, 80)
            elif i <= 4: col = (220, 180, 20)
            else:        col = (220, 60,  50)
            pygame.draw.rect(screen, col, (bx, y - seg_h // 2, seg_w, seg_h))
            # Highlight
            pygame.draw.rect(screen, (255, 255, 255),
                             (bx, y - seg_h // 2, seg_w, 3))

# ── HUD: race position badge ──────────────────────────────────────────────────

def draw_place_badge(screen: pygame.Surface,
                     place: int, x: int, y: int) -> None:
    """Flash-style placement badge with border."""
    labels = {1: "1ST", 2: "2ND", 3: "3RD", 4: "4TH"}
    colors = {1: (255, 205,   0),
              2: (200, 200, 215),
              3: (205, 127,  50),
              4: (160, 160, 175)}
    label = labels.get(place, f"{place}TH")
    color = colors.get(place, s.white)
    # Panel
    draw_panel(screen, x, y, 88, 50, color=s.FLASH_PANEL_BG, alpha=220)
    bx, by = x - 44, y - 25
    pygame.draw.rect(screen, color, (bx, by, 88, 50), 2)
    draw_text(screen, label, 30, color, x, y)


# ── Timer bar ─────────────────────────────────────────────────────────────────

def draw_timer_bar(screen: pygame.Surface,
                   time_remaining: float, max_time: float) -> None:
    """Flash-style timer bar — taller, bolder, colour-coded urgency."""
    bar_w, bar_h = 280, 18
    bx = s.screen_width // 2 - bar_w // 2
    by = 4

    # Background track
    pygame.draw.rect(screen, (25, 25, 38), (bx, by, bar_w, bar_h))

    ratio  = max(0.0, time_remaining / max_time)
    fill_w = int(bar_w * ratio)

    # Colour transitions: green → amber → red
    if ratio > 0.6:
        bar_col = (40, 210, 80)
    elif ratio > 0.3:
        bar_col = (220, 160, 20)
    else:
        bar_col = (220, 50, 50)

    if fill_w > 0:
        pygame.draw.rect(screen, bar_col, (bx, by, fill_w, bar_h))
        # Inner highlight stripe
        pygame.draw.rect(screen, (255, 255, 255),
                         (bx, by, fill_w, 3), 0)

    # Border
    pygame.draw.rect(screen, s.FLASH_PANEL_BORDER, (bx, by, bar_w, bar_h), 1)

    # Time label
    draw_text(screen, f"{max(0.0, time_remaining):.1f}s",
              14, s.white, s.screen_width // 2, by + bar_h + 12)

# ── Leaderboard ───────────────────────────────────────────────────────────────

def draw_leaderboard(screen: pygame.Surface, racers: list,
                     checkpoint_clusters: list,
                     current_turn: int) -> None:
    """
    Condensed leaderboard: shows only the player, the racer
    immediately ahead, and the racer immediately behind

    """
    import settings as s
    total_cp = len(checkpoint_clusters)

    def score(r):
        if r.crashed:   return (-1, 0, 0)
        if r.finished:  return (100, -(r.finish_turn or 9999), 0)
        cp   = len(r.checkpoints_cleared)
        dist = float("inf")
        if cp < total_cp:
            cl   = checkpoint_clusters[cp]
            cx_  = sum(tx for tx, _ in cl) / len(cl)
            cy_  = sum(ty for _, ty in cl) / len(cl)
            dist = abs(r.state.x - cx_) + abs(r.state.y - cy_)
        return (1, cp, -dist)

    ranked = sorted(racers, key=score, reverse=True)

    # Find player rank (0-indexed)
    player_rank = next((i for i, r in enumerate(ranked) if r.type == "PLAYER"), 0)

    # Build the 3-entry window: [one ahead, player, one behind]
    lo = max(0, player_rank - 1)
    hi = min(len(ranked), player_rank + 2)
    visible = ranked[lo:hi]

    # Layout constants
    cx      = s.screen_width - 110
    start_y = 105           # below speed/lives panel (~y=75)
    row_h   = 26
    panel_h = 18 + row_h * len(visible)
    panel_w = 220

    draw_panel(screen, cx, start_y + panel_h // 2 - 4,
               panel_w, panel_h + 16,
               color=s.FLASH_PANEL_BG, alpha=210)
    # Border
    bx = cx - panel_w // 2
    by = start_y - 8
    pygame.draw.rect(screen, s.FLASH_PANEL_BORDER,
                     (bx, by, panel_w, panel_h + 16), 1)

    labels = ["1st", "2nd", "3rd", "4th"]
    y = start_y

    for global_rank, racer in enumerate(ranked):
        if racer not in visible:
            continue
        cp     = len(racer.checkpoints_cleared)
        place  = labels[global_rank] if global_rank < 4 else f"{global_rank+1}th"
        is_player = (racer.type == "PLAYER")

        if racer.finished:
            status = "DONE"
        elif racer.crashed:
            status = "OUT"
        else:
            status = f"L{racer.laps_completed + 1} · {cp}/{total_cp}cp"

        # Highlight player row
        if is_player:
            highlight_surf = pygame.Surface((panel_w - 4, row_h - 2), pygame.SRCALPHA)
            highlight_surf.fill((255, 255, 255, 18))
            screen.blit(highlight_surf, (bx + 2, y - row_h // 2 + 1))

        col = s.FLASH_GOLD if is_player else racer.color
        draw_text(screen, f"{place}  {racer.name}", 13, col, cx - 28, y)
        draw_text(screen, status, 12, (180, 180, 200) if not is_player else s.white,
                  cx + 60, y, bold=False)
        y += row_h

    # Separator + turn counter
    pygame.draw.line(screen, s.FLASH_PANEL_BORDER,
                     (bx + 6, y - 4), (bx + panel_w - 6, y - 4), 1)
    draw_text(screen, f"Turn {current_turn}", 11, (130, 130, 155),
              cx, y + 4, bold=False)

# ── Menu list ─────────────────────────────────────────────────────────────────

def draw_menu_list(screen: pygame.Surface,
                   items: list[str], selected: int,
                   cx: int, top_y: int,
                   item_height: int = 52) -> None:
    """Vertical list of menu items with selection highlight."""
    for i, item in enumerate(items):
        y      = top_y + i * item_height
        active = i == selected
        if active:
            draw_panel(screen, cx, y, 420, item_height - 6,
                       color=(40, 40, 60), alpha=200)
            pygame.draw.rect(screen, s.yellow,
                             (cx - 210, y - (item_height - 6) // 2,
                              420, item_height - 6), 2)
        prefix = "▶  " if active else "   "
        color  = s.yellow if active else (190, 190, 190)
        draw_text(screen, prefix + item, 26, color, cx, y)


# ── Decorative background ─────────────────────────────────────────────────────

def draw_boot_background(screen: pygame.Surface) -> None:
    """Gradient-ish dark background for states where no track is loaded."""
    for row in range(s.screen_height):
        ratio = row / s.screen_height
        r = int(8  + 12 * ratio)
        g = int(8  +  8 * ratio)
        b = int(20 + 20 * ratio)
        pygame.draw.line(screen, (r, g, b), (0, row), (s.screen_width, row))

# ── Weather badge ─────────────────────────────────────────────────
def draw_weather_badge(screen: pygame.Surface, weather: str) -> None:
    """
    Small pill shown in the top-centre of the RUNNING and PRE_RACE screens.
    Colour-codes the current weather mode so it's always visible at a glance.
    """
    colour = s.WEATHER_COLOURS.get(weather, s.white)
    label  = s.WEATHER_LABELS.get(weather, weather)
    draw_panel(screen, s.screen_width // 2, 28, 120, 26, alpha=155)
    draw_text(screen, label, 14, colour,
              s.screen_width // 2, 28, bold=False)

# ── obstacle rendering ──────────────────────────────────────────────
def draw_obstacles(screen: pygame.Surface,
                   obstacles: list,
                   tile_size: int) -> None:
    """
    Render all active obstacles on the track surface.

    OilSpill — dark iridescent ellipse with colour-sheen rings.
    Pothole  — rough dark cavity with interior crack lines.

    Both use SRCALPHA surfaces so they composite cleanly over any track theme.
    """
    for obs in obstacles:
        if not obs.active:
            continue
        px   = obs.x * tile_size
        py   = obs.y * tile_size
        half = tile_size // 2

        surf = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)

        if obs.type == "OilSpill":
            # Dark base puddle
            pygame.draw.ellipse(surf, (15, 10, 25, 215),
                                (2, 4, tile_size - 4, tile_size - 7))
            # Iridescent sheen rings
            for i, col in enumerate(
                    [(90, 10, 120, 110), (10, 80, 110, 100), (80, 90, 10, 80)]):
                pygame.draw.ellipse(surf, col,
                                    (3 + i, 5 + i,
                                     tile_size - 6 - i * 2,
                                     tile_size - 9 - i * 2), 1)

        elif obs.type == "Pothole":
            # Dark rough cavity
            pygame.draw.rect(surf, (28, 16, 6, 245),
                             (3, 3, tile_size - 6, tile_size - 6))
            pygame.draw.rect(surf, (70, 44, 18, 190),
                             (3, 3, tile_size - 6, tile_size - 6), 1)
            # Interior crack lines for texture
            mid = tile_size // 2
            pygame.draw.line(surf, (55, 34, 14, 160), (5, mid), (mid, 5), 1)
            pygame.draw.line(surf, (55, 34, 14, 160),
                             (mid, tile_size - 5), (tile_size - 5, mid), 1)

        screen.blit(surf, (px, py))

# ── GA setup screen ─────────────────────────────────────────────────

def draw_ga_setup(screen: pygame.Surface,
                  waypoints: int,
                  sharpness_idx: int) -> None:
    """
    Full-screen parameter selection UI rendered inside the GA_SETUP state.

    Controls (handled in main.py event loop):
      Left / Right  — adjust waypoint count (4-10)
      Up / Down     — cycle sharpness preset
      SPACE         — confirm and begin generation
      ESC / Back    — return to BOOT_MENU
    """
    cx = s.screen_width  // 2
    cy = s.screen_height // 2

    draw_text(screen, "TRACK GENERATION SETTINGS", 40, s.yellow, cx, 80)
    pygame.draw.line(screen, (60, 60, 80),
                     (160, 122), (s.screen_width - 160, 122), 1)

    # ── Waypoint count ────────────────────────────────────────────────────────
    draw_text(screen, "NUMBER OF TURNS", 18, (160, 160, 180), cx, cy - 100)

    draw_text(screen, "<",  26, s.cyan,  cx - 80, cy - 65)
    draw_text(screen, ">",  26, s.cyan,  cx + 80, cy - 65)
    draw_panel(screen, cx, cy - 65, 76, 40, color=(30, 30, 50), alpha=210)
    draw_text(screen, str(waypoints), 30, s.white, cx, cy - 65)
    draw_text(screen, "4 = simple loop    10 = complex circuit",
              14, (110, 110, 130), cx, cy - 36, bold=False)

    # ── Sharpness presets ─────────────────────────────────────────────────────
    draw_text(screen, "TURN SHARPNESS", 18, (160, 160, 180), cx, cy + 14)

    descriptions = {
        "Gentle": "Wide sweeping curves — easier to navigate.",
        "Normal": "Balanced mix of straights and bends.",
        "Sharp":  "Tight hairpins — demanding but exciting.",
    }

    for i, name in enumerate(s.GA_SHARPNESS_NAMES):
        iy     = cy + 50 + i * 46
        active = (i == sharpness_idx)
        pcol   = (40, 40, 60) if active else (14, 14, 24)
        draw_panel(screen, cx, iy, 280, 38, color=pcol, alpha=210)
        if active:
            pygame.draw.rect(screen, s.yellow,
                             (cx - 140, iy - 19, 280, 38), 1)
        color  = s.yellow if active else (150, 150, 160)
        prefix = "> " if active else "  "
        draw_text(screen, prefix + name, 22, color, cx, iy)

    # Description for the currently selected preset
    sel_name = s.GA_SHARPNESS_NAMES[sharpness_idx]
    draw_text(screen, descriptions.get(sel_name, ""),
              14, (130, 130, 150), cx, cy + 198, bold=False)

    # ── Key hints ─────────────────────────────────────────────────────────────
    pygame.draw.line(screen, (60, 60, 80),
                     (160, s.screen_height - 62),
                     (s.screen_width - 160, s.screen_height - 62), 1)
    draw_text(screen,
              "< >  Adjust turns    Up/Dn  Sharpness    SPACE  Generate    ESC  Back",
              13, (90, 90, 110), cx, s.screen_height - 36, bold=False)
    # ── Static A* path preview (replaces incremental node animation) ──────────────

def draw_static_path_preview(screen: pygame.Surface,
                              preview_path: list,
                              track,
                              alpha: int) -> None:
    """
    Render the full optimal A* path as a single polyline that fades in.

    The path is drawn onto a dedicated SRCALPHA surface at the requested
    alpha (0–255) so the fade-in is a simple alpha ramp in the caller —
    no incremental reveal, no frame counters, no accumulation surface.

    The line is drawn in two passes:
      1. A thicker, darker stroke for contrast against light track surfaces.
      2. A thinner bright-green stroke on top.

    Parameters
    ----------
    preview_path : list[CarState]
        The ordered list returned by solver.solve().
    track        : Track
        Used for TILE_SIZE to convert grid coords → pixel coords.
    alpha        : int  [0–255]
        Current opacity; caller increments this each frame.
    """
    if not preview_path or alpha <= 0:
        return

    ts   = track.TILE_SIZE
    pts  = [
        (st.x * ts + ts // 2, st.y * ts + ts // 2)
        for st in preview_path
    ]
    if len(pts) < 2:
        return

    # Build once per call onto an SRCALPHA surface so alpha blending works
    surf = pygame.Surface((s.screen_width, s.screen_height), pygame.SRCALPHA)

    # Pass 1: dark shadow stroke (contrast)
    pygame.draw.lines(surf, (0, 80, 0, alpha), False, pts, 5)
    # Pass 2: bright green stroke
    pygame.draw.lines(surf, (50, 255, 80, alpha), False, pts, 2)

    # Dot at each waypoint so corners are visible
    for px, py in pts[::max(1, len(pts) // 60)]:   # sample ~60 dots max
        pygame.draw.circle(surf, (50, 255, 80, min(alpha, 160)), (px, py), 2)

    screen.blit(surf, (0, 0))
    
# ── Wrong way banner ──────────────────────────────────────────────────────────

def draw_wrong_way_banner(screen: pygame.Surface) -> None:
    """
    Pulsing red 'WRONG WAY' banner displayed while the player moves
    significantly against the circuit direction.

    Purely cosmetic — no physics are altered.
    The pulse uses a faster sine frequency than draw_pulsing_text so it
    reads as urgent rather than decorative.
    """
    pulse = (math.sin(time.time() * 8.0 * math.pi) + 1) / 2
    alpha = int(160 + 95 * pulse)

    # Dark red panel behind the text
    draw_panel(screen,
               s.screen_width // 2,
               s.screen_height // 2 - 60,
               380, 70,
               color=(120, 0, 0), alpha=200)

    # Bright text on top with its own pulse
    draw_text(screen,
              "WRONG WAY",
              46,
              (255, 55, 55),
              s.screen_width // 2,
              s.screen_height // 2 - 60,
              alpha=alpha)

# ── Track naming overlay ──────────────────────────────────────────────────────

def draw_naming_overlay(screen: pygame.Surface, name_buffer: str) -> None:
    """
    Render a centred text-input prompt over the PRE_RACE screen.

    Parameters
    ----------
    name_buffer : str
        The character sequence typed so far (does not include .json extension).
    """
    # Dim the screen behind the prompt
    draw_overlay(screen, alpha=160, color=(0, 0, 20))

    draw_panel(screen,
               s.screen_width  // 2,
               s.screen_height // 2,
               560, 140,
               color=(10, 10, 30), alpha=230)

    draw_text(screen,
              "Name this track",
              22, (180, 180, 200),
              s.screen_width // 2,
              s.screen_height // 2 - 36,
              bold=False)

    # Blinking cursor — toggles every 0.5s
    cursor = "|" if int(time.time() * 2) % 2 == 0 else " "

    # Display the typed name, or a placeholder when empty
    display = (name_buffer + cursor) if name_buffer else (f"custom_track_{cursor}")
    color   = s.white if name_buffer else (100, 100, 120)

    draw_text(screen,
              display,
              28, color,
              s.screen_width // 2,
              s.screen_height // 2 + 4)

    draw_text(screen,
              "RETURN  confirm     ESC  use default name     BACKSPACE  delete",
              13, (90, 90, 110),
              s.screen_width // 2,
              s.screen_height // 2 + 46,
              bold=False)
    
# ── Track leaderboard ─────────────────────────────────────────────

def draw_track_leaderboard(screen: pygame.Surface,
                            leaderboard: list,
                            cx: int, cy: int) -> None:
    """
    Render the top-5 persistent leaderboard for the current track.

    Parameters
    ----------
    leaderboard : list of {"name": str, "turns": int, "date": str}
        Sorted ascending by turns (best first).  At most 5 entries.
    cx, cy : int
        Centre pixel of the panel.
    """
    if not leaderboard:
        return

    panel_w = 340
    row_h   = 28
    panel_h = 40 + row_h * len(leaderboard)

    draw_panel(screen, cx, cy, panel_w, panel_h, color=(0, 0, 20), alpha=210)

    draw_text(screen, "Best Runs",
              16, (160, 160, 190),
              cx, cy - panel_h // 2 + 16, bold=False)

    medal_colors = [
        (255, 215,   0),   # 1st — gold
        (192, 192, 192),   # 2nd — silver
        (205, 127,  50),   # 3rd — bronze
        (180, 180, 180),   # 4th
        (160, 160, 160),   # 5th
    ]

    for rank, entry in enumerate(leaderboard):
        ry    = cy - panel_h // 2 + 36 + rank * row_h
        col   = medal_colors[rank] if rank < len(medal_colors) else s.white
        label = f"{rank + 1}.  {entry['name']}"
        turns = f"{entry['turns']} turns"
        date  = entry.get("date", "")

        # Left-aligned name with rank
        draw_text(screen, label, 14, col,
                  cx - panel_w // 2 + 70, ry, bold=(rank == 0))

        # Right-aligned turn count
        draw_text(screen, turns, 13, col,
                  cx + panel_w // 2 - 70, ry, bold=False)

        # Date in muted smaller text
        if date:
            draw_text(screen, date, 11, (100, 100, 120),
                      cx, ry + 12, bold=False) 