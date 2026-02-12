# display_utils.py
import time
from .ht16k33_driver import display_text_all_modules, clear_all, NUM_MODULES, DISPLAY_PER_MODULE


def show_text(text, delay=0.3):
    """
    Zeigt einen Text auf allen Modulen an.
    - Scrollt automatisch, wenn der Text länger als die Gesamtanzeige ist.
    - Zeigt einfach an, wenn der Text kürzer oder gleich lang ist.
    """
    total_chars = NUM_MODULES * DISPLAY_PER_MODULE
    
    if len(text) <= total_chars:
        # Text passt auf alle Module, kein Scrollen nötig
        display_text_all_modules(text)
    else:
        # Text ist länger, scrollen
        padded_text = text + ' ' * total_chars  # Leerzeichen am Ende für sanftes Auslaufen
        for i in range(len(padded_text) - total_chars + 1):
            window = padded_text[i:i + total_chars]
            display_text_all_modules(window)
            time.sleep(delay)
    
    # Optional: kurz Pause am Ende
    time.sleep(delay)
