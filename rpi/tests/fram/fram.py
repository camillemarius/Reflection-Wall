"""
fram.py

MB85RC256VPNF I2C FRAM
32KB Speicher
"""

from smbus2 import SMBus


class FRAM:

    SIZE = 32768

    def __init__(self, bus=1, address=0x50):
        self.bus = SMBus(bus)
        self.address = address

    def write(self, addr, data):
        self._check(addr, len(data))

        data = list(data)

        while data:
            chunk = data[:30]
            data = data[30:]

            self.bus.write_i2c_block_data(
                self.address,
                (addr >> 8) & 0xFF,
                [addr & 0xFF] + chunk
            )

            addr += len(chunk)


    def read(self, addr, length):
        self._check(addr, length)

        self.bus.write_i2c_block_data(
            self.address,
            (addr >> 8) & 0xFF,
            [addr & 0xFF]
        )

        return bytes(
            self.bus.read_i2c_block_data(
                self.address,
                0,
                length
            )
        )


    def write_string(self, addr, text):
        self.write(
            addr,
            text.encode()
        )


    def read_string(self, addr, length):
        return self.read(
            addr,
            length
        ).decode(
            errors="ignore"
        )


    def clear(self):
        block = bytes(32)

        for addr in range(0, self.SIZE, 32):
            self.write(addr, block)


    def _check(self, addr, length):
        if addr < 0 or addr + length > self.SIZE:
            raise ValueError(
                "FRAM address error"
            )


    def close(self):
        self.bus.close()


    def __enter__(self):
        return self


    def __exit__(self, *args):
        self.close()