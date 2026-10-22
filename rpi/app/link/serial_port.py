"""Serieller Port zum ESP (ttyAMA0) mit Umschalter GPIO23 auf LOW = ESP."""
import serial

ESP_DEVICE = "/dev/ttyAMA0"
ESP_BAUD = 74880  # E2-a; Z12: sonst 115200 auf beiden Seiten (ESP: Features::LINK_BAUD)
UART_SELECT_GPIO = 23  # LOW = ESP (F1)
GPIO_CHIP = 0  # wie driver/uart/uart_switch.py
READ_TIMEOUT_S = 0.05


class SerialPort:
    def __init__(self, serial: "serial.SerialBase", gpio_handle: int | None = None,
                 lgpio_module=None) -> None:
        self._serial = serial
        self._gpio_handle = gpio_handle
        self._lgpio = lgpio_module

    def read_available(self) -> bytes:
        return self._serial.read(max(1, self._serial.in_waiting))

    def write(self, data: bytes) -> None:
        self._serial.write(data)
        self._serial.flush()

    def close(self) -> None:
        try:
            self._serial.close()
        finally:
            if self._gpio_handle is not None:
                handle, self._gpio_handle = self._gpio_handle, None
                if self._lgpio is None:
                    import lgpio as lgpio_module  # erst hier: auf dem PC nicht installiert
                    self._lgpio = lgpio_module
                self._lgpio.gpiochip_close(handle)


def open_esp_port(device: str = ESP_DEVICE, baud: int = ESP_BAUD,
                  select_gpio: bool = True, lgpio_module=None) -> SerialPort:
    handle = None
    lgpio = None
    if select_gpio:
        if lgpio_module is None:
            import lgpio as lgpio_module  # erst hier: auf dem PC nicht installiert
        lgpio = lgpio_module
        handle = lgpio.gpiochip_open(GPIO_CHIP)
        try:
            lgpio.gpio_claim_output(handle, UART_SELECT_GPIO, 0)
        except Exception:
            lgpio.gpiochip_close(handle)
            raise
    try:
        ser = serial.serial_for_url(device, baudrate=baud, timeout=READ_TIMEOUT_S)
    except Exception:
        if handle is not None:
            lgpio.gpiochip_close(handle)
        raise
    return SerialPort(ser, handle, lgpio)
