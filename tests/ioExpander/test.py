from pcf8575 import PCF8575
from gpio_events import GPIOEventManager


def taste_changed(pin, value):
    print(f"P{pin:02d} geändert -> {value}")


def taste_pressed(pin):
    print(f"P{pin:02d} gedrückt")


def taste_released(pin):
    print(f"P{pin:02d} losgelassen")



pcf = PCF8575(
    bus=1,
    address=0x20,
    int_gpio=4
)


events = GPIOEventManager(pcf)


events.on_change(
    3,
    taste_changed
)


events.on_falling(
    4,
    taste_pressed
)


events.on_rising(
    4,
    taste_released
)


pcf.enable_interrupt()



while True:
    pass