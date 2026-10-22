#pragma once
// Serielle Schnittstelle zum Pi, ohne Arduino.
#include <string>

class ISerialPort
{
public:
    virtual ~ISerialPort() = default;
    virtual int read() = 0;                           // naechstes Byte 0..255, -1 wenn keines wartet
    virtual void write(const std::string& bytes) = 0;
};
