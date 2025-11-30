import pygame
import settings as s

class Track:
    def _init_(self, image_path):
        try:  #.convert optimizes image fir faster blitting
            self.track_surface = pygame.image.load(image_path).convert()
            self.track_surface = pugame.transform.scale(
                self.track_surface, (s.screen_width, s.screen_height)
            )
        except pygame.error as e:
            print(f"Error loading track image: {e}")
            #create blank fallback track
            self.track_surface = pygame.Surface((s.screen_width, s.screen_height))
            self.track_surface.fill(s.track_colour)  #safe track colour
        
        self.track_rect = self.track_surface: get_rect()
    
    def draw(self, screen):
        """Draws the track surface onto the main screen"""
        screen.blit(self.track_surface, (0, 0))
    
    def validate_move(self, start_vec, end_vec):
        """check line from start to end for collision
        returns: "crash", "finish" or "ok"
        """
        #colour from single pixel helper
        
        def get_pixel_colour(pos):
            pixel = (int(pos.x), int(pos.y))
            #is pixel off the map
            if not self.track_rect.collidepoint(pixel):
                return "CRASH"
            try:
                colour = self.track_surface.get_at(pixel)
                #rgb values
                if (colour.r, colour.g, colour.b) = s.wall_colour:
                    return "CRASH"
                if (colour.r, colour.g, colour.b) = s.finish_colour:
                    return "FINISH"
                return "OK"  ##if everything else is okay
            except IndexError:
                #if int() rounding pushes off edge
                return "CRASH"
        
        #check end point
        end_status = get_pixel_colour(end_vec)
        if end_status == "CRASH":
            return "CRASH"

        #chech path (interpolation)
        line_vec = end_vec - start_vec
        total_distance = line_vec.length()

        if total_distance == 0:
            return "OK"  #not moving is always ok
        
        step_vec = line_vec.normalize()  #direction
        steps = int(total_distance)  #check one pixel per unit distance
        
        #check every pixel on the path
        for i in range(1, steps, + 1):
            current_pos = start_vec + step_vec * i
            path_status = get_pixel_colour(current_pos)

            if path_status == "CRASH":
                return "CRASH"  #hits wall during move
            
            if path_status == "FINISH":
                return "FINISH"  #cross finish during move
        
        #if path is clear, return final landing spot
        return end_status

            
