#include "UartPort.h"

UartPort::UartPort(HardwareSerial& serial)
    : _serial(serial)
{
}

int UartPort::read()
{
    return _serial.read();
}

void UartPort::write(const std::string& bytes)
{
    _serial.write(reinterpret_cast<const uint8_t*>(bytes.data()), bytes.size());
}
