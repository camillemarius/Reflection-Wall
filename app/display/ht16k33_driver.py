# ht16k33_driver.py
import smbus2 as smbus
import time
# ht16k33_driver.py
from .ascii_map import ASCII_16SEG   # relativer Import innerhalb des Packages

# HT16K33 Base address
HT16K33_BASE_ADDR = 0x70
NUM_MODULES = 12  # 12 ICs
DISPLAY_PER_MODULE = 8  # 8x 16-Segment per module

# I2C bus (Raspberry Pi usually 1)
bus = smbus.SMBus(1)

# Segment buffer for all modules
segment_buffers = [[0x00] * 16 for _ in range(NUM_MODULES)]

# HT16K33 Commands
CMD_SYSTEM_SETUP = 0x20
CMD_DISPLAY_SETUP = 0x80
CMD_BRIGHTNESS = 0xE0

# Initialize all modules
def init_ht16k33():
    for i in range(NUM_MODULES):
        addr = HT16K33_BASE_ADDR + i
        try:
            bus.write_byte(addr, CMD_SYSTEM_SETUP | 0x01)  # oscillator on
            bus.write_byte(addr, CMD_DISPLAY_SETUP | 0x01) # display on, no blink
            bus.write_byte(addr, CMD_BRIGHTNESS | 0x0F)   # max brightness
        except OSError as e:
            print(f"[WARN] Kein Gerät an Adresse 0x{addr:02X} erreichbar: {e}")


# Update a module's display from buffer
def update_module(module_idx):
    addr = HT16K33_BASE_ADDR + module_idx
    data = segment_buffers[module_idx]
    bus.write_i2c_block_data(addr, 0x00, data)

# Set a 16-segment digit
def set_digit(module_idx, digit_idx, segments):
    if module_idx >= NUM_MODULES or digit_idx >= DISPLAY_PER_MODULE:
        return
    low = segments & 0xFF
    high = (segments >> 8) & 0xFF
    segment_buffers[module_idx][digit_idx * 2] = low
    segment_buffers[module_idx][digit_idx * 2 + 1] = high

# Clear a module
def clear_module(module_idx):
    segment_buffers[module_idx] = [0x00] * 16
    update_module(module_idx)

# Clear all modules
def clear_all():
    for i in range(NUM_MODULES):
        clear_module(i)

# Display a character on a specific module and digit
def display_char(module_idx, digit_idx, char):
    segments = ASCII_16SEG.get(char.upper(), 0x0000)
    set_digit(module_idx, digit_idx, segments)
    update_module(module_idx)

# Display a string across a module
# text: string (max 8 chars per module)
def display_text(module_idx, text):
    for i in range(DISPLAY_PER_MODULE):
        if i < len(text):
            display_char(module_idx, i, text[i])
        else:
            set_digit(module_idx, i, 0x0000)
    update_module(module_idx)

def display_text_all_modules(text):
    """
    Zeigt einen langen Text über alle Module hinweg an.
    Jedes Modul hat DISPLAY_PER_MODULE Zeichen.
    """
    text_len = len(text)
    for module_idx in range(NUM_MODULES):
        # Textsegment für dieses Modul
        start = module_idx * DISPLAY_PER_MODULE
        end = start + DISPLAY_PER_MODULE
        segment_text = text[start:end]
        display_text(module_idx, segment_text)




