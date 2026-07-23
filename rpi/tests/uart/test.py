from esp_controller import ESPController
import time


text = """
Die Temperatur im Raum ist zu hoch.
Bitte Lüftung einschalten.
Der aktuelle Messwert beträgt 28 Grad.
"""



def get_text():
    return text

esp = ESPController(text_provider=get_text, port="/dev/serial0")

try:
    while True:
        esp.loop()
        time.sleep(0.01)

except KeyboardInterrupt:
    esp.close()