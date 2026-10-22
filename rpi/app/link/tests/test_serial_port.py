import unittest

from app.link.codec import Message
from app.link.pi_link import PiLink
from app.link.serial_port import ESP_BAUD, UART_SELECT_GPIO, open_esp_port


class FakeLgpio:
    def __init__(self):
        self.calls = []

    def gpiochip_open(self, chip):
        self.calls.append(("open", chip))
        return 7

    def gpio_claim_output(self, handle, gpio, level=0):
        self.calls.append(("claim", handle, gpio, level))

    def gpio_write(self, handle, gpio, level):
        self.calls.append(("write", handle, gpio, level))

    def gpiochip_close(self, handle):
        self.calls.append(("close", handle))


class SerialPortTest(unittest.TestCase):
    def test_loop_port_round_trip_through_link(self):
        port = open_esp_port("loop://", select_gpio=False)
        link = PiLink(port)
        self.addCleanup(port.close)
        self.addCleanup(link.stop)
        link.start()
        self.assertEqual(link.request("PING").result(timeout=2), Message(0, "PONG"))

    def test_gpio_is_claimed_low_and_released_on_close(self):
        gpio = FakeLgpio()
        port = open_esp_port("loop://", select_gpio=True, lgpio_module=gpio)
        self.assertIn(("claim", 7, UART_SELECT_GPIO, 0), gpio.calls)
        self.assertEqual(ESP_BAUD, 74880)
        port.close()
        self.assertIn(("close", 7), gpio.calls)


if __name__ == "__main__":
    unittest.main()
