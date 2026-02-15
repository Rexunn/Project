import pygame

#SCREEN DIMENSION
screen_width = 1000
screen_height = 800

#FRAMES
fps = 30  #no need for fast frames for turn based

#COLOURS -- predefined
white = (255, 255, 255)
black = (0, 0, 0) #walls
gray = (255, 0, 0)  #road
red = (255, 0, 0)
green = (0, 255, 0)  # finish line
blue = (0, 0, 255)
yellow = (255, 255, 0) #checkpoints

#GAME SPECIFIC COLOURS
bg_colour = white
wall_colour = black
finish_colour = green
track_colour = gray
checkpoint_colour = yellow

#GHOST COLOURS
ghost = (100, 100, 255, 150)  #semi-transparent blue
ghost_crash = (255, 100, 100, 150)  #semi-transparent red
ghost_finish = (100, 255, 100, 150) #semi-transparent green