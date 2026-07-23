"""
pcf8575.py

Treiber für PCF8575 (16 Bit I2C GPIO Expander)

Hardwarebelegung:
-----------------

Outputs:
    P00 P01 P02 P13 P14 P15

Inputs:
    P03 P04 P05 P10 P11 P12

Unused:
    P06-P09

Interrupt:
    PCF8575 INT -> Raspberry Pi GPIO4 (BCM)

Benötigt:
    pip install smbus2 lgpio
"""

from smbus2 import SMBus
import lgpio


# ---------------------------------------------------------
# Pin-Konfiguration
# ---------------------------------------------------------

OUTPUT_MASK = (
    (1 << 0)  |   # P00
    (1 << 1)  |   # P01
    (1 << 2)  |   # P02
    (1 << 13) |   # P13
    (1 << 14) |   # P14
    (1 << 15)     # P15
)


INPUT_MASK = (
    (1 << 3)  |   # P03
    (1 << 4)  |   # P04
    (1 << 5)  |   # P05
    (1 << 10) |   # P10
    (1 << 11) |   # P11
    (1 << 12)     # P12
)


UNUSED_MASK = 0xFFFF & ~(OUTPUT_MASK | INPUT_MASK)



class PCF8575:


    def __init__(
        self,
        bus=1,
        address=0x20,
        gpio_chip=0,
        int_gpio=4
    ):

        self.address = address

        self.bus = SMBus(bus)


        # Callbacks
        self._callbacks = []


        # Interrupt
        self._gpio_chip = gpio_chip
        self._int_gpio = int_gpio

        self._chip = None
        self._interrupt = None


        #
        # Initialzustand:
        #
        # Outputs LOW
        # Inputs HIGH (= Eingang)
        # Unused HIGH
        #

        self._state = (
            INPUT_MASK |
            UNUSED_MASK
        )


        self.write_port(
            self._state
        )


        # Zustand synchronisieren
        self._state = self.read_port()



    # -----------------------------------------------------
    # Schliessen
    # -----------------------------------------------------

    def close(self):

        if self._interrupt:

            self._interrupt.cancel()
            self._interrupt = None


        if self._chip:

            lgpio.gpiochip_close(
                self._chip
            )

            self._chip = None


        self.bus.close()



    # -----------------------------------------------------
    # Port Zugriff
    # -----------------------------------------------------

    def write_port(
        self,
        value
    ):

        value &= 0xFFFF


        low = value & 0xFF

        high = (
            value >> 8
        ) & 0xFF


        self.bus.write_i2c_block_data(
            self.address,
            low,
            [high]
        )


        self._state = value



    def read_port(self):

        data = self.bus.read_i2c_block_data(
            self.address,
            0,
            2
        )


        value = (
            data[0] |
            (data[1] << 8)
        )


        self._state = value


        return value



    # -----------------------------------------------------
    # Pin lesen
    # -----------------------------------------------------

    def read_pin(
        self,
        pin
    ):

        if not (INPUT_MASK & (1 << pin)):

            raise ValueError(
                f"P{pin:02d} ist kein Eingang"
            )


        value = self.read_port()


        return (
            value >> pin
        ) & 1



    # -----------------------------------------------------
    # Pin schreiben
    # -----------------------------------------------------

    def write_pin(
        self,
        pin,
        level
    ):

        if not (OUTPUT_MASK & (1 << pin)):

            raise ValueError(
                f"P{pin:02d} ist kein Ausgang"
            )


        if level:

            self._state |= (
                1 << pin
            )

        else:

            self._state &= ~(
                1 << pin
            )


        self.write_port(
            self._state
        )



    # -----------------------------------------------------
    # Ausgang toggeln
    # -----------------------------------------------------

    def toggle_pin(
        self,
        pin
    ):

        if not (OUTPUT_MASK & (1 << pin)):

            raise ValueError(
                f"P{pin:02d} ist kein Ausgang"
            )


        self._state ^= (
            1 << pin
        )


        self.write_port(
            self._state
        )



    # -----------------------------------------------------
    # Callback
    # -----------------------------------------------------

    def register_callback(
        self,
        callback
    ):
        """
        Callback:

        callback(
            changed_mask,
            new_state,
            old_state
        )

        """

        self._callbacks.append(
            callback
        )



    # -----------------------------------------------------
    # Interrupt aktivieren
    # -----------------------------------------------------

    def enable_interrupt(self):


        self._chip = lgpio.gpiochip_open(
            self._gpio_chip
        )


        lgpio.gpio_claim_input(
            self._chip,
            self._int_gpio,
            lgpio.SET_PULL_UP
        )


        self._interrupt = lgpio.callback(
            self._chip,
            self._int_gpio,
            lgpio.FALLING_EDGE,
            self._interrupt_handler
        )



    # -----------------------------------------------------
    # Interrupt Handler
    # -----------------------------------------------------

    def _interrupt_handler(
        self,
        chip,
        gpio,
        level,
        timestamp
    ):


        old_state = self._state


        data = self.bus.read_i2c_block_data(
            self.address,
            0,
            2
        )


        new_state = (
            data[0] |
            (data[1] << 8)
        )


        self._state = new_state



        changed = (
            old_state ^
            new_state
        )


        #
        # Nur Eingänge berücksichtigen
        #

        changed &= INPUT_MASK



        if changed == 0:

            return



        for callback in self._callbacks:

            callback(
                changed,
                new_state,
                old_state
            )



    # -----------------------------------------------------
    # Context Manager
    # -----------------------------------------------------

    def __enter__(self):

        return self



    def __exit__(
        self,
        exc_type,
        exc,
        tb
    ):

        self.close()