class CarState:
    """
    Stores the snapshot of a car at a specific moment (Discrete State).
    Used for the A* Algorithm to remember where it has been.
    """
    def __init__(self, x, y, vx, vy):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy

    #tells Python how to check if two states are the same
    def __eq__(self, other):
        return (self.x, self.y, self.vx, self.vy) == (other.x, other.y, other.vx, other.vy)

    #allows object to be put into a Set or Dictionary
    def __hash__(self):
        return hash((self.x, self.y, self.vx, self.vy))

    #helper for debugging
    def __repr__(self):
        return f"Car(x={self.x}, y={self.y}, vx={self.vx}, vy={self.vy})"