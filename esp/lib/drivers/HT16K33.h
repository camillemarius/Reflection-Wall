#pragma once

#include <Arduino.h>
#include <Wire.h>

class HT16K33
{
public:

    static constexpr uint8_t CHARS_PER_MODULE = 8;
    static constexpr uint8_t BUFFER_SIZE = CHARS_PER_MODULE * 2;

    HT16K33(uint8_t address);

    void begin();
    void clear();

    void setText(const String& text);

    void setBrightness(uint8_t level);

<<<<<<< HEAD
    bool testConnection();

    uint8_t testConnectionCode();

    uint8_t getAddress() const;

=======
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61
private:

    uint8_t _address;

    uint8_t _buffer[BUFFER_SIZE];

    void init();
    void write();

<<<<<<< HEAD
    void clearBuffer();

=======
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61
    void setChar(uint8_t position, char c);
};