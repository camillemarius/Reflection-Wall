#pragma once
// Die serielle Leitung zum Pi als ISerialPort (Serial, 74 880 Baud, siehe Features::LINK_BAUD).
#include <Arduino.h>
#include <string>
#include "ISerialPort.h"

class UartPort : public ISerialPort
{
public:
    explicit UartPort(HardwareSerial& serial);
    int read() override;                              // serial.read(), -1 wenn leer
    void write(const std::string& bytes) override;    // serial.write(data, size), ohne flush

private:
    HardwareSerial& _serial;
};
