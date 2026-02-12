# core/segment_module.py
from app.driver.ht16k33_driver import create_empty_buffer, set_digit, write_buffer, CHARS_PER_MODULE

class SegmentModule:
    def __init__(self, module_index):
        self.module_index = module_index
        self.chars_per_module = CHARS_PER_MODULE
        self.buffer = create_empty_buffer()

    def clear(self):
        self.buffer = create_empty_buffer()
        write_buffer(self.module_index, self.buffer)

    def set_text(self, text):
        for i in range(self.chars_per_module):
            char = text[i] if i < len(text) else " "
            set_digit(self.buffer, i, char)  # <-- Hier übergibst du einfach Buchstaben
        write_buffer(self.module_index, self.buffer)
