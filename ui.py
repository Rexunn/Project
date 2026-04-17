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
    """Five segmented bars coloured green / yellow / red by speed."""
    speed = max(abs(vx), abs(vy))
    draw_text(screen, "SPD", 12, (180, 180, 180), x - 30, y, bold=False)
    for i in range(1, 6):
        seg = (50, 50, 50)
        if i <= speed:
            if   i <= 2: seg = s.green
            elif i <= 4: seg = s.yellow
            else:        seg = s.red
        pygame.draw.rect(screen, seg, (x - 8 + (i - 1) * 14, y - 7, 10, 14))


# ── HUD: race position badge ──────────────────────────────────────────────────

def draw_place_badge(screen: pygame.Surface,
                     place: int, x: int, y: int) -> None:
    """Large top-left placement badge (1ST / 2ND / …)."""
    labels = {1: "1ST", 2: "2ND", 3: "3RD", 4: "4TH"}
    colors = {1: s.yellow, 2: (210, 210, 210), 3: (205, 127, 50), 4: s.white}
    label = labels.get(place, f"{place}TH")
    color = colors.get(place, s.white)
    draw_panel(screen, x, y, 80, 46, color=(0, 0, 0), alpha=170)
    draw_text(screen, label, 28, color, x, y)


# ── Timer bar ─────────────────────────────────────────────────────────────────

def draw_timer_bar(screen: pygame.Surface,
                   time_remaining: float, max_time: float) -> None:
    bar_w, bar_h = 260, 14
    bx = s.screen_width // 2 - bar_w // 2
    by = 6
    pygame.draw.rect(screen, (40, 40, 40), (bx, by, bar_w, bar_h))
    ratio   = max(0.0, time_remaining / max_time)
    fill_w  = int(bar_w * ratio)
    bar_col = s.green if ratio > 0.33 else s.red
    if fill_w > 0:
        pygame.draw.rect(screen, bar_col, (bx, by, fill_w, bar_h))
    pygame.draw.rect(screen, (120, 120, 120), (bx, by, bar_w, bar_h), 1)
    draw_text(screen, f"{max(0.0, time_remaining):.1f}s", 13, s.white,
              s.screen_width // 2, by + bar_h + 11)


# ── Leaderboard ───────────────────────────────────────────────────────────────

def draw_leaderboard(screen: pygame.Surface, racers: list,
                     checkpoint_clusters: list,
                     current_turn: int) -> None:
    """Compact mid-right leaderboard, sorted by race progress."""
    total_cp = len(checkpoint_clusters)
    x = s.screen_width - 160
    y = 90                               # start below the top-right HUD

    draw_panel(screen, x, y + 50, 300, 150, alpha=140)

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

    for i, racer in enumerate(sorted(racers, key=score, reverse=True)):
        cp     = len(racer.checkpoints_cleared)
        labels = ["1st", "2nd", "3rd", "4th"]
        place  = labels[i] if i < 4 else f"{i+1}th"
        if racer.finished:
            status = "DONE"
        elif racer.crashed:
            status = "OUT"
        else:
            status = f"L{racer.laps_completed + 1} {cp}/{total_cp}cp"
        draw_text(screen, f"{place} {racer.name}: {status}",
                  13, racer.color, x, y)
        y += 18

        if racer.type == "CPU_HARD" and racer.precomputed_path:
            draw_text(screen,
                      f"  A* {len(racer.precomputed_path)}st "
                      f"{len(racer.explored_states)}n "
                      f"{racer.solve_time:.2f}s",
                      11, (160, 160, 160), x, y)
            y += 15

    y += 8
    draw_text(screen, f"Turn {current_turn}", 12, (160, 160, 160), x, y)


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
