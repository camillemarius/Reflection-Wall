import smbus2 as smbus
from .ascii_map import ASCII_16SEG  # ASCII-Mapping muss vorhanden sein

HT16K33_BASE_ADDR = 0x70
bus = smbus.SMBus(1)

CMD_SYSTEM_SETUP = 0x20
CMD_DISPLAY_SETUP = 0x80
CMD_BRIGHTNESS = 0xE0

CHARS_PER_MODULE = 8
BYTES_PER_MODULE = CHARS_PER_MODULE * 2

# -------------------
# Basisfunktionen
# -------------------

def init_module(module_index):
    """Initialisiert ein einzelnes Modul"""
    addr = HT16K33_BASE_ADDR + module_index
    try:
        bus.write_byte(addr, CMD_SYSTEM_SETUP | 0x01)
        bus.write_byte(addr, CMD_DISPLAY_SETUP | 0x01)
        bus.write_byte(addr, CMD_BRIGHTNESS | 0x0F)
    except OSError as e:
        print(f"[WARN] Kein Gerät an Adresse 0x{addr:02X} erreichbar: {e}")

def create_empty_buffer():
    """16-Byte-Buffer für ein Modul"""
    return [0x00] * BYTES_PER_MODULE

def set_digit(buffer, digit_idx, char):
    """Setzt ein Zeichen auf ein Modul-Buffer"""
    if digit_idx >= CHARS_PER_MODULE:
        return
    segments = ASCII_16SEG.get(char.upper(), 0x0000)
    buffer[digit_idx * 2] = segments & 0xFF
    buffer[digit_idx * 2 + 1] = (segments >> 8) & 0xFF

def write_buffer(module_index, buffer):
    addr = HT16K33_BASE_ADDR + module_index
    try:
        bus.write_i2c_block_data(addr, 0x00, buffer)
    except OSError as e:
        print(f"[WARN] Schreiben fehlgeschlagen an 0x{addr:02X}: {e}")

def clear_module(buffer):
    """Setzt alle Bytes eines Buffers auf 0"""
    for i in range(BYTES_PER_MODULE):
        buffer[i] = 0x00

# ----- Simulation -----
class TestModule:
    """Platzhalter für Terminal-Simulation"""
    def __init__(self, index, chars_per_module=CHARS_PER_MODULE):
        self.index = index
        self.chars_per_module = chars_per_module
        self.chars = chars_per_module
        self.buffer = [" "] * chars_per_module

    def clear(self):
        self.buffer = [" "] * self.chars_per_module

    def set_text(self, text):
        for i in range(self.chars_per_module):
            self.buffer[i] = text[i] if i < len(text) else " "

# ----- Echtes Modul -----
class I2CModule:
    """Repräsentiert ein echtes HT16K33-Modul über I2C"""
    def __init__(self, index, chars_per_module=CHARS_PER_MODULE):
        self.index = index
        self.chars_per_module = chars_per_module
        self.chars = chars_per_module
        self.buffer = create_empty_buffer()
        init_module(index)

    def clear(self):
        clear_module(self.buffer)
        write_buffer(self.index, self.buffer)

    def set_text(self, text):
        for i in range(self.chars_per_module):
            char = text[i] if i < len(text) else " "
            set_digit(self.buffer, i, char)
        write_buffer(self.index, self.buffer)

# ----- Helper für alle Module -----
def init_ht16k33(total_modules):
    """Initialisiert alle Module"""
    for i in range(total_modules):
        init_module(i)

def clear_all(modules):
    """Löscht alle Module"""
    for mod in modules:
        mod.clear()
