import smbus2 as smbus
import time
from ascii_16seg import ASCII_16SEG

HT16K33_ADDR = 0x72
bus = smbus.SMBus(1)
buffer = [0x00] * 16

# ----------------------------
# Initialisierung
# ----------------------------
def init_ht16k33():
    bus.write_byte(HT16K33_ADDR, 0x21)  # System einschalten
    bus.write_byte(HT16K33_ADDR, 0x81)  # Display an
    bus.write_byte(HT16K33_ADDR, 0xEF)  # Helligkeit max

def write_display():
    bus.write_i2c_block_data(HT16K33_ADDR, 0x00, buffer)

def set_digit_raw(hex_value, digit_idx):
    if not (0 <= digit_idx <= 7):
        return
    addr = digit_idx * 2
    buffer[addr] = hex_value & 0xFF
    buffer[addr + 1] = (hex_value >> 8) & 0xFF

# ----------------------------
# Text auf Display schreiben
# ----------------------------
def display_text(text):
    text = text.ljust(8)[:8]  # genau 8 Zeichen
    for i, char in enumerate(text):
        hex_value = ASCII_16SEG.get(char.upper(), 0x0000)
        set_digit_raw(hex_value, i)
    write_display()
    print(f"Anzeige: '{text}'")

# ----------------------------
# Lauflicht für längere Texte
# ----------------------------
def scroll_text(text, delay=0.3):
    if len(text) <= 8:
        display_text(text)
        return
    
    # Padding links/rechts für flüssiges Scrollen
    text = ' ' * 8 + text + ' ' * 8
    
    for i in range(len(text) - 7):
        window = text[i:i+8]
        display_text(window)
        time.sleep(delay)

# ----------------------------
# Beispiel
# ----------------------------
init_ht16k33()

# Endlosschleife: Text scrollen
while True:
    scroll_text("CAMILLE IST DER CHEFF.", delay=0.5)