"""
uart_switch.py

GPIO23:
LOW  = ESP verbunden
HIGH = getrennt
"""


import lgpio
import time



class UARTSwitch:


    def __init__(
        self,
        gpio=23,
        chip=0
    ):

        self.gpio = gpio


        self.handle = lgpio.gpiochip_open(
            chip
        )


        lgpio.gpio_claim_output(
            self.handle,
            gpio
        )


        self.disable()



    def enable(self):

        lgpio.gpio_write(
            self.handle,
            self.gpio,
            0
        )

        time.sleep(
            0.05
        )



    def disable(self):

        lgpio.gpio_write(
            self.handle,
            self.gpio,
            1
        )

        time.sleep(
            0.05
        )



    def close(self):

        self.disable()

        lgpio.gpiochip_close(
            self.handle
        )