#pragma once

#include <Arduino.h>
#include <cstddef>
#include <cstdint>

#include "SlotStore.h"

// MB85RC256V (32 KB) auf I2C 0x50, 16-Bit-Adresse, hoeherwertiges Byte zuerst.
// Fuer das FRAM wird der Bus auf 100 kHz getaktet; danach steht er auf
// jedem Weg wieder auf I2CMasterControl::I2C_CLOCK_HZ.
class FramBus : public IByteStore
{
public:
    static constexpr uint8_t ADDRESS = 0x50;
    static constexpr std::size_t CHUNK = 32;
    static constexpr uint32_t CLOCK_HZ = 100000;   // nur fuer das FRAM
    static constexpr std::size_t SIZE = 0x8000;

    bool read(uint16_t address, uint8_t* out, std::size_t length) override;
    bool write(uint16_t address, const uint8_t* data, std::size_t length) override;
};
