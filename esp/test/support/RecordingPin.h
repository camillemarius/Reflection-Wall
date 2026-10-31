#pragma once

#include <string>
#include "PiPower.h"

// Zeichnet auf, was PiPower am Pin tut: "R" lesen, "H"/"L" ausgeben,
// "W50" warten, durch Leerzeichen getrennt. Warten stellt die
// Uhr now vor; nowMs() erscheint nicht im Log.
class RecordingPin : public IPowerPin
{
public:
    bool idle = true;   // Pegel, den readIdle() liefert
    unsigned long now = 0;  // was nowMs() liefert
    std::string log;

    bool readIdle() override
    {
        add("R");
        return idle;
    }

    void drive(bool high) override
    {
        add(high ? "H" : "L");
    }

    void waitMs(unsigned long ms) override
    {
        add("W" + std::to_string(ms));
        now += ms;
    }

    unsigned long nowMs() override
    {
        return now;
    }

private:
    void add(const std::string& s)
    {
        if (!log.empty())
            log += " ";
        log += s;
    }
};
