from .uart_switch import UARTSwitch

class UARTDevice:

    def __init__(self, uart):
        self.uart = uart

    @property
    def device(self):
        raise NotImplementedError

    def select(self):
        self.uart.select(self.device)

    def write(self, data):
        self.select()
        self.uart.write(data)

    def read(self, size=1):
        self.select()
        return self.uart.read(size)

    def readline(self):
        self.select()
        return self.uart.readline()

    @property
    def available(self):
        self.select()
        return self.uart.available