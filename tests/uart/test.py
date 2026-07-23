from esp_uart_text import SwitchedESPTextUART


text = """
Die Temperatur im Raum ist zu hoch.
Bitte Lüftung einschalten.
Der aktuelle Messwert beträgt 28 Grad.
"""


with SwitchedESPTextUART(
    port="/dev/serial0"
) as esp:

    if esp.send_text(text):

        print("Text erfolgreich gespeichert")

    else:

        print("ESP keine Antwort")