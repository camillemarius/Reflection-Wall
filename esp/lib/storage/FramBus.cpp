#include "FramBus.h"

#include <Wire.h>
#include "I2CMasterControl.h"

namespace
{
    // Klammert einen Buszugriff: Bus ein, 100 kHz; beim Verlassen
    // (jeder Weg) wieder 10 kHz und Bus frei.
    class BusSession
    {
    public:
        BusSession()
        {
            I2CMasterControl::enable();
            Wire.setClock(FramBus::CLOCK_HZ);
        }

        ~BusSession()
        {
            Wire.setClock(I2CMasterControl::I2C_CLOCK_HZ);
            Wire.setSdaHold(I2C_SDA_HOLD_US);   // erst nach setClock: die Haltezeit wird an die Halbperiode geklemmt
            I2CMasterControl::disable();
        }
    };

    bool inRange(uint16_t address, std::size_t length)
    {
        return static_cast<std::size_t>(address) + length <= FramBus::SIZE;
    }

    void sendAddress(uint16_t address)
    {
        Wire.beginTransmission(FramBus::ADDRESS);
        Wire.write(static_cast<uint8_t>(address >> 8));
        Wire.write(static_cast<uint8_t>(address & 0xFF));
    }
}

bool FramBus::read(uint16_t address, uint8_t* out, std::size_t length)
{
    if (!inRange(address, length))
        return false;

    BusSession session;

    std::size_t done = 0;
    while (done < length)
    {
        const std::size_t n = (length - done < CHUNK) ? (length - done) : CHUNK;

        sendAddress(static_cast<uint16_t>(address + done));
        if (Wire.endTransmission(false) != 0)
            return false;

        if (Wire.requestFrom(ADDRESS, static_cast<uint8_t>(n)) != n)
            return false;

        for (std::size_t i = 0; i < n; ++i)
            out[done + i] = static_cast<uint8_t>(Wire.read());

        done += n;
        yield();
    }
    return true;
}

bool FramBus::write(uint16_t address, const uint8_t* data, std::size_t length)
{
    if (!inRange(address, length))
        return false;

    BusSession session;

    std::size_t done = 0;
    while (done < length)
    {
        const std::size_t n = (length - done < CHUNK) ? (length - done) : CHUNK;

        sendAddress(static_cast<uint16_t>(address + done));
        Wire.write(data + done, n);
        if (Wire.endTransmission() != 0)
            return false;

        done += n;
        yield();
    }
    return true;
}
