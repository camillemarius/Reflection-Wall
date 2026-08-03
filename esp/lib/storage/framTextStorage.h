#pragma once

#include <Arduino.h>
#include <Wire.h>

#include "ITextStorage.h"

class FramTextStorage : public ITextStorage
{
public:
    explicit FramTextStorage(uint8_t address = 0x50);

    bool begin() override;

    bool writeText(const String& text) override;

    String readText() override;

    void clear() override;

private:
    bool writeByte(uint16_t address, uint8_t data);
    uint8_t readByte(uint16_t address);

    bool writeBlock(uint16_t address, const uint8_t* data, uint16_t length);
    bool readBlock(uint16_t address, uint8_t* data, uint16_t length);

private:
    uint8_t _address;

    static constexpr uint16_t TEXT_ADDRESS = 0x0000;
    static constexpr uint16_t MAX_TEXT_LENGTH = 1024;
};