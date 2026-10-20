#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>
#include "SlotStore.h"

// 32 KB Speicher fuer Tests; writeBudget >= 0 simuliert einen Reset mitten im Schreiben:
// Nach so vielen geschriebenen Bytes scheitert jedes weitere write, die Bytes davor stehen schon da
class MemoryBytes : public IByteStore
{
public:
    std::vector<uint8_t> data = std::vector<uint8_t>(32768, 0x00);
    bool failRead = false;
    bool failWrite = false;
    long writeBudget = -1;

    bool read(uint16_t address, uint8_t* out, std::size_t length) override
    {
        if (failRead || static_cast<std::size_t>(address) + length > data.size())
        {
            return false;
        }
        for (std::size_t i = 0; i < length; ++i)
        {
            out[i] = data[address + i];
        }
        return true;
    }

    bool write(uint16_t address, const uint8_t* in, std::size_t length) override
    {
        if (failWrite || static_cast<std::size_t>(address) + length > data.size())
        {
            return false;
        }
        for (std::size_t i = 0; i < length; ++i)
        {
            if (writeBudget == 0)
            {
                return false;
            }
            data[address + i] = in[i];
            if (writeBudget > 0)
            {
                --writeBudget;
            }
        }
        return true;
    }
};
