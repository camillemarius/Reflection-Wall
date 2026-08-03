#pragma once

#include <Arduino.h>
#include <Wire.h>

class PCF8575
{
public:
    explicit PCF8575(uint8_t address = 0x20);

    bool begin();

    bool write16(uint16_t value);

    uint16_t read16();

    bool digitalWrite(uint8_t pin, bool state);

    bool digitalRead(uint8_t pin);

    void setOutput(uint8_t pin, bool state);

    void clear();


private:
    uint8_t _address;
    uint16_t _state;
};