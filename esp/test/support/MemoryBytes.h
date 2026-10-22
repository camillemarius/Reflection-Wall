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
    int corruptReads = 0;          // > 0: jedes Lesen ueber 16 Bytes kippt ein Byte, Zaehler sinkt
    int corruptHeaderReads = 0;    // > 0: jedes Lesen von genau 16 Bytes kippt Bits, Zaehler sinkt
    std::size_t headerFlipByte = 4;
    uint8_t headerFlipMask = 0x04;
    bool corruptWrites = false;    // jedes Schreiben ueber 16 Bytes speichert ein gekipptes Byte

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
        if (corruptHeaderReads > 0 && length == 16)
        {
            out[headerFlipByte] ^= headerFlipMask;
            --corruptHeaderReads;
        }
        if (corruptReads > 0 && length > 16)
        {
            out[length / 2] ^= 0x01;
            --corruptReads;
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
        if (corruptWrites && length > 16)
        {
            data[address + length / 2] ^= 0x01;
        }
        return true;
    }
};
