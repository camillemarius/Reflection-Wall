#include "Crc32.h"

uint32_t crc32Ieee(const uint8_t* data, std::size_t length, uint32_t crc)
{
    crc = ~crc;
    for (std::size_t i = 0; i < length; ++i)
    {
        crc ^= data[i];
        for (int bit = 0; bit < 8; ++bit)
        {
            crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
        }
    }
    return ~crc;
}
