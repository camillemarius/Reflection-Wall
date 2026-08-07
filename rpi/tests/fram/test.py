"""
test_fram_text.py

Test für MB85RC256VPNF
mit ESP-kompatiblem Textformat
"""

from fram_text_storage import FramTextStorage


storage = FramTextStorage()

try:

    if not storage.begin():
        print("FRAM nicht gefunden")
        exit()


    text = """
Temperatur zu hoch.
Bitte Lüftung einschalten.
"""


    if storage.write_text(text):
        print("Schreiben OK")
    else:
        print("Schreiben FEHLER")


    result = storage.read_text()

    print("Gelesen:")
    print(result)


    if result.strip() == text.strip():
        print("Test OK")
    else:
        print("Daten unterschiedlich")


finally:

    storage.close()