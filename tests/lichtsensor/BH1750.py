"""
bh1750.py

Treiber für ROHM BH1750FVI Digital Light Sensor

Features:
---------
- I2C Kommunikation
- Lux Messung
- High Resolution Mode
- Low Resolution Mode
- Continuous Measurement
- One Shot Measurement
- Context Manager

Benötigt:
---------
pip install smbus2

Adresse:
--------
ADDR LOW  -> 0x23
ADDR HIGH -> 0x5C
"""


from smbus2 import SMBus
import time



class BH1750:


    # -------------------------------------------------
    # Kommandos
    # -------------------------------------------------

    POWER_DOWN = 0x00
    POWER_ON   = 0x01
    RESET      = 0x07

    # Continuous Measurement
    CONTINUOUS_HIGH_RES   = 0x10
    CONTINUOUS_HIGH_RES_2 = 0x11
    CONTINUOUS_LOW_RES    = 0x13


    # One Shot Measurement
    ONE_TIME_HIGH_RES   = 0x20
    ONE_TIME_HIGH_RES_2 = 0x21
    ONE_TIME_LOW_RES    = 0x23

    # Messzeiten in Sekunden
    MEASUREMENT_TIME = {
        CONTINUOUS_HIGH_RES:
            0.180,
        CONTINUOUS_HIGH_RES_2:
            0.180,
        CONTINUOUS_LOW_RES:
            0.024,
        ONE_TIME_HIGH_RES:
            0.180,
        ONE_TIME_HIGH_RES_2:
            0.180,
        ONE_TIME_LOW_RES:
            0.024
    }

    ONE_SHOT_MODES = (
        ONE_TIME_HIGH_RES,
        ONE_TIME_HIGH_RES_2,
        ONE_TIME_LOW_RES
    )

    def __init__(
        self,
        bus=1,
        address=0x23,
        mode=CONTINUOUS_HIGH_RES
    ):

        if address not in (
            0x23,
            0x5C
        ):
            raise ValueError(
                "BH1750 Adresse muss 0x23 oder 0x5C sein"
            )

        self.bus = SMBus(bus)
        self.address = address
        self.mode = None

        self.power_on()
        self.reset()

        self.set_mode(
            mode
        )

    # -------------------------------------------------
    # Grundfunktionen
    # -------------------------------------------------
    def close(self):
        self.power_down()
        self.bus.close()

    def power_on(self):
        self.bus.write_byte(
            self.address,
            self.POWER_ON
        )

    def power_down(self):
        self.bus.write_byte(
            self.address,
            self.POWER_DOWN
        )

    def reset(self):
        self.power_on()
        time.sleep(
            0.005
        )
        self.bus.write_byte(
            self.address,
            self.RESET
        )

    # -------------------------------------------------
    # Modus
    # -------------------------------------------------
    def set_mode(
        self,
        mode
    ):
        
        if mode not in self.MEASUREMENT_TIME:

            raise ValueError(
                "Ungültiger BH1750 Messmodus"
            )

        self.bus.write_byte(
            self.address,
            mode
        )

        self.mode = mode

    # -------------------------------------------------
    # Messung
    # -------------------------------------------------

    def read_raw(self):
        """
        Liefert den 16 Bit Sensorwert
        """
        data = self.bus.read_i2c_block_data(
            self.address,
            0,
            2
        )
        return (
            (data[0] << 8)
            |
            data[1]
        )

    def read_lux(self):
        """
        Liefert Messwert in Lux
        """
        #
        # One Shot:
        # Messung erst starten
        #
        if self.mode in self.ONE_SHOT_MODES:

            self.bus.write_byte(
                self.address,
                self.mode
            )

            time.sleep(
                self.MEASUREMENT_TIME[self.mode]
            )

        raw = self.read_raw()

        #
        # BH1750 Auflösung
        #
        lux = raw / 1.2
        return lux



    # -------------------------------------------------
    # Diagnose
    # -------------------------------------------------

    def __repr__(self):

        return (
            f"<BH1750 "
            f"addr=0x{self.address:02X}, "
            f"mode=0x{self.mode:02X}>"
        )



    # -------------------------------------------------
    # Context Manager
    # -------------------------------------------------

    def __enter__(self):

        return self



    def __exit__(
        self,
        exc_type,
        exc,
        tb
    ):

        self.close()