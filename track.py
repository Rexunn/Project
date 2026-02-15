import pygame
import settings as s

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
        """converts pixels to grid values using fuzzy color matching"""
        self.grid = []
        for r in range(self.rows):
            row_data = []
            for c in range(self.cols):
                px_x = c * self.TILE_SIZE + (self.TILE_SIZE // 2)
                px_y = r * self.TILE_SIZE + (self.TILE_SIZE // 2)
                
                try:
                    color = self.surface.get_at((px_x, px_y))
                    rgb = (color.r, color.g, color.b)
                    
                    # fuzzy matching - checks ranges instead of exact values
                    
                    # check for black (wall) - very low light
                    if rgb[0] < 50 and rgb[1] < 50 and rgb[2] < 50:
                        row_data.append(0)
                        
                    # check for yellow (checkpoint) - high red, high green, low blue
                    elif rgb[0] > 200 and rgb[1] > 200 and rgb[2] < 100:
                        row_data.append(4)
                        
                    # check for green (finish) - low red, high green, low blue
                    elif rgb[0] < 100 and rgb[1] > 200 and rgb[2] < 100:
                        row_data.append(3)
                        
                    # check for blue (start) - low red, low green, high blue
                    elif rgb[0] < 100 and rgb[1] < 100 and rgb[2] > 200:
                        row_data.append(2)
                        
                    # everything else is road (red/gray)
                    else:
                        row_data.append(1)
                        
                except IndexError:
                    row_data.append(0) #off screen
            
            self.grid.append(row_data)

    def draw(self, screen):
        """Visualise the grid for debugging"""
        # 1. Draw the actual image of the track (walls and road)
        screen.blit(self.surface, (0, 0))

        # 2. Draw debug markers (Start/Finish) on top
        for r in range(self.rows):
            for c in range(self.cols):
                val = self.grid[r][c]
                rect = (c * self.TILE_SIZE, r * self.TILE_SIZE, self.TILE_SIZE, self.TILE_SIZE)
                
                if val == 2: #start
                    pygame.draw.rect(screen, s.blue, rect) 
                elif val == 3: #finish
                    pygame.draw.rect(screen, s.finish_colour, rect)