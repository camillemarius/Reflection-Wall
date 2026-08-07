"""
test_uart_system.py

Test für:
- UARTMaster
- UARTESP
- UARTHLK
"""

from uart_master import UARTMaster
from uart_esp import UARTESP
from uart_hlk import UARTHLK

import time


text = """
Hello from ESP8266
"""


def get_text():
    return text


def print_hlk(hlk):
    data = hlk.get_data()

    print(
        "HLK:",
        "Present=", data.presence,
        "Moving=", data.moving,
        "Stationary=", data.stationary,
        "Distance=", data.distance, "cm",
        "Energy=", data.energy
    )


def print_esp_test(esp):
    print("ESP Test")
    esp.send("TEST", "Hallo ESP")


uart = UARTMaster()
esp = UARTESP(uart, text_provider=get_text)
hlk = UARTHLK(uart)


print("UART System gestartet")
print("Aktives Gerät:", uart.device)


last_hlk_print = 0
last_esp_test = 0


try:
    while True:

        now = time.time()

        # ESP bearbeiten
        esp.update()


        # HLK Daten lesen
        hlk.update()


        # HLK Status jede Sekunde ausgeben
        if now - last_hlk_print > 1:

            print_hlk(hlk)

            last_hlk_print = now


        # ESP Test alle 10 Sekunden
        if now - last_esp_test > 10:

            print_esp_test(esp)

            last_esp_test = now


        time.sleep(0.01)


except KeyboardInterrupt:

    print("\nBeende Test")

finally:

    uart.close()

    print("UART geschlossen")