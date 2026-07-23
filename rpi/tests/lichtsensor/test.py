from bh1750 import BH1750
import time


with BH1750(
    bus=1,
    address=0x23
) as sensor:


    print(sensor)


    while True:

        lux = sensor.read_lux()

        print(
            f"{lux:.1f} Lux"
        )

        time.sleep(1)