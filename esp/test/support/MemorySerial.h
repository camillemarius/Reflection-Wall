#pragma once
#include <string>
#include "ISerialPort.h"

class MemorySerial : public ISerialPort
{
public:
    std::string rx;   // was "der Pi" schickt; read() nimmt vorne weg
    std::string tx;   // was der ESP geschrieben hat

    int read() override
    {
        if (rx.empty()) return -1;
        int c = static_cast<unsigned char>(rx[0]);
        rx.erase(0, 1);
        return c;
    }
    void write(const std::string& bytes) override { tx += bytes; }
    std::string takeTx()
    {
        std::string t;
        t.swap(tx);
        return t;
    }
};
