# ui/animations.py
import time

def typewriter(grid, lines, delay=0.05):
    max_len = max(len(line) for line in lines)
    for i in range(1, max_len + 1):
        partial = [line[:i] for line in lines]
        grid.set_text(partial)
        time.sleep(delay)
