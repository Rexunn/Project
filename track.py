import pygame
import settings as s
import json
import os

class Track:  #rename to match main
    def __init__(self, image_path):
        """
        Loads an image and converts it into a 2D Grid (List of Lists).
        Logic: Scans pixels based on TILE_SIZE to build the grid.
        """
        #define grid size
        self.TILE_SIZE = 20  
        self.cols = s.screen_width // self.TILE_SIZE
        self.rows = s.screen_height // self.TILE_SIZE
        
        self.grid = []
        
        try:
            #load image
            self.surface = pygame.image.load(image_path)
            #resize to fit screen
            self.surface = pygame.transform.scale(self.surface, (s.screen_width, s.screen_height))
            print(f"Track loaded. Generating {self.cols}x{self.rows} grid...")
            self._image_to_grid()
        except FileNotFoundError:
            print(f"Error: Could not find {image_path}. Make sure the image is in the same folder.")
            self.grid = [[0 for _ in range(self.cols)] for _ in range(self.rows)]#empty fallback

    def _image_to_grid(self):
        """
        Scans the ENTIRE 20x20 tile for walls, not just the center dot.
        This fixes the 'Thin Wall' problem by inflating walls to fill the grid.
        """
        self.grid = []
        for r in range(self.rows):
            row_data = []
            for c in range(self.cols):

                # Default to Road (1)
                tile_value = 1

                # SCANNER: Check a 3x3 grid of sample points within the tile
                # This ensures we catch the line even if it's off-center
                found_wall = False
                found_checkpoint = False
                found_finish = False
                found_start = False

                # Define sample offsets (Top-Left, Center, Bottom-Right, etc.)
                offsets = [5, 10, 15]

                for dy in offsets:
                    for dx in offsets:
                        px_x = c * self.TILE_SIZE + dx
                        px_y = r * self.TILE_SIZE + dy

                        try:
                            color = self.surface.get_at((px_x, px_y))
                            rgb = (color.r, color.g, color.b)

                            # PRIORITY 1: WALL (Black)
                            if rgb[0] < 80 and rgb[1] < 80 and rgb[2] < 80:
                                found_wall = True

                            # PRIORITY 2: CHECKPOINT (Yellow)
                            elif rgb[0] > 200 and rgb[1] > 200 and rgb[2] < 100:
                                found_checkpoint = True

                            # PRIORITY 3: FINISH (Green)
                            elif rgb[0] < 100 and rgb[1] > 200 and rgb[2] < 100:
                                found_finish = True

                            # PRIORITY 4: START (Blue)
                            elif rgb[0] < 100 and rgb[1] < 100 and rgb[2] > 200:
                                found_start = True

                        except IndexError:
                            pass # Ignore off-screen

                # DECISION LOGIC: Wall overrides everything
                if found_wall:
                    tile_value = 0
                elif found_checkpoint:
                    tile_value = 4
                elif found_finish:
                    tile_value = 3
                elif found_start:
                    tile_value = 2

                row_data.append(tile_value)

            self.grid.append(row_data)

    # --- BUILD TRACK FROM GA GRID (no image needed) ---

    @classmethod
    def from_grid(cls, grid):
        """
        Build a Track directly from a 2D grid (from the GA).
        Skips image loading entirely - renders tiles as coloured rectangles.
        """
        track = cls.__new__(cls)  #create instance without calling __init__
        track.TILE_SIZE = 20
        track.cols = s.screen_width // track.TILE_SIZE
        track.rows = s.screen_height // track.TILE_SIZE
        track.grid = grid

        # Build a pygame surface from the grid
        track.surface = track._grid_to_surface()
        print(f"Track built from GA grid. {track.cols}x{track.rows}")
        return track

    def _grid_to_surface(self):
        """Convert the grid into a pygame surface for drawing"""
        surface = pygame.Surface((s.screen_width, s.screen_height))
        import random

        # Define some visual themes for the walls and road
        themes = [
            {0: s.black, 1: s.gray},                         # Classic Tarmac
            {0: (30, 60, 30), 1: (120, 90, 60)},             # Forest Dirt Track
            {0: (10, 10, 40), 1: (50, 200, 200)},            # Cyberpunk Neon
            {0: (200, 200, 220), 1: (240, 240, 255)}         # Snow/Ice
        ]
        
        # Pick a random theme for this specific map
        current_theme = random.choice(themes)

        # Colour map: grid value -> colour
        colours = {
            0: current_theme[0], # wall color from theme
            1: current_theme[1], # road color from theme
            2: s.blue,           # start
            3: s.green,          # finish
            4: s.yellow,         # checkpoint
        }

        for r in range(self.rows):
            for c in range(self.cols):
                val = self.grid[r][c]
                colour = colours.get(val, s.gray)
                rect = (c * self.TILE_SIZE, r * self.TILE_SIZE, self.TILE_SIZE, self.TILE_SIZE)
                pygame.draw.rect(surface, colour, rect)

        return surface

    def draw(self, screen):
        """Visualise the grid for debugging"""
        # Draw the actual image of the track (walls and road)
        screen.blit(self.surface, (0, 0))

        # Draw debug markers (Start/Finish) on top
        for r in range(self.rows):
            for c in range(self.cols):
                val = self.grid[r][c]
                rect = (c * self.TILE_SIZE, r * self.TILE_SIZE, self.TILE_SIZE, self.TILE_SIZE)

                if val == 2: #start
                    pygame.draw.rect(screen, s.blue, rect)
                elif val == 3: #finish
                    pygame.draw.rect(screen, s.finish_colour, rect)
   # --- FILE SAVING & LOADING ---

    def save_to_file(self, filename="saved_track.json"):
        """Saves the current grid to a JSON file"""
        with open(filename, 'w') as f:
            json.dump(self.grid, f)
        print(f"Track saved successfully to {filename}!")

    @classmethod
    def from_file(cls, filename):
        """Loads a track directly from a saved JSON grid"""
        try:
            with open(filename, 'r') as f:
                grid = json.load(f)
            return cls.from_grid(grid)
        except FileNotFoundError:
            print(f"Error: Could not find {filename}")
            return None