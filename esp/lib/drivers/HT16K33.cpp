#include "HT16K33.h"

#include "ASCII16Seg.h"
#include "pinMapping.h"


HT16K33::HT16K33(uint8_t address)
{
    _address = address;
    clearBuffer();
}


void HT16K33::begin()
{
    init();

}


void HT16K33::init()
{
    // System oscillator ON
    Wire.beginTransmission(_address);
    Wire.write(0x20 | 0x01);
    Wire.endTransmission();


    // Display ON + no blink
    Wire.beginTransmission(_address);
    Wire.write(0x80 | 0x01);
    Wire.endTransmission();


    setBrightness(DEFAULT_BRIGHTNESS);
}


void HT16K33::setBrightness(uint8_t level)
{
    if(level > MAX_BRIGHTNESS)
        level = MAX_BRIGHTNESS;


    Wire.beginTransmission(_address);
    Wire.write(0xE0 | level);
    Wire.endTransmission();
}


void HT16K33::setDisplayOn(bool on)
{
    Wire.beginTransmission(_address);
    Wire.write(0x80 | (on ? 0x01 : 0x00));
    Wire.endTransmission();
}


bool HT16K33::testConnection()
{
    return testConnectionCode() == 0;
}


uint8_t HT16K33::testConnectionCode()
{
    Wire.beginTransmission(_address);
    Wire.write(0x20 | 0x01);

    return Wire.endTransmission();
}


uint8_t HT16K33::getAddress() const
{
    return _address;
}


void HT16K33::clear()
{
    clearBuffer();
    write();
}


void HT16K33::clearBuffer()
{
    memset(_buffer, 0, sizeof(_buffer));
}


void HT16K33::setChar(uint8_t position, char c)
{
    if(position >= CHARS_PER_MODULE)
        return;


    // Punkt an vorheriges Zeichen anhängen
    if(c == '.')
    {
        if(position == 0)
            return;


        uint16_t seg =
            _buffer[(position - 1) * 2] |
            (_buffer[(position - 1) * 2 + 1] << 8);


        seg |= ASCII16Seg::get('.');


        _buffer[(position - 1) * 2] = seg & 0xFF;
        _buffer[(position - 1) * 2 + 1] = seg >> 8;

        return;
    }


    uint16_t seg = ASCII16Seg::get(c);


    _buffer[position * 2] = seg & 0xFF;
    _buffer[position * 2 + 1] = seg >> 8;
}


void HT16K33::setText(const String& text)
{
    clearBuffer();


    for(uint8_t i = 0; i < CHARS_PER_MODULE; i++)
    {
        if(i < text.length())
            setChar(i, text[i]);
        else
            setChar(i, ' ');
    }


    write();
}


void HT16K33::write()
{
    for(uint8_t attempt = 0; attempt < WRITE_ATTEMPTS; attempt++)
    {
        if(attempt > 0)
            _retries++;

        Wire.beginTransmission(_address);
        Wire.write(0x00);

        for(uint8_t i = 0; i < BUFFER_SIZE; i++)
        {
            Wire.write(_buffer[i]);
        }

        _lastError = Wire.endTransmission();

        if(_lastError == 0)
            return;
    }
}


uint8_t HT16K33::lastWriteError() const
{
    return _lastError;
}


uint8_t HT16K33::writeRetries() const
{
    return _retries;
}


void HT16K33::resetWriteStats()
{
    _lastError = 0;
    _retries = 0;
}

void HT16K33::testAllSegments()
{
    for (uint8_t i = 0; i < BUFFER_SIZE; i++)
        _buffer[i] = 0xFF;

    write();
}