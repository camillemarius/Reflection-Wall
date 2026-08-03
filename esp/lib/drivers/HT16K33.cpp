#include "HT16K33.h"

#include "ASCII16Seg.h"
#include "I2CMasterControl.h"


HT16K33::HT16K33(uint8_t address)
{
    _address = address;
    clear();
}


void HT16K33::begin()
{
    Wire.begin();

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


    setBrightness(15);
}


void HT16K33::setBrightness(uint8_t level)
{
    if(level > 15)
        level = 15;


    Wire.beginTransmission(_address);
    Wire.write(0xE0 | level);
    Wire.endTransmission();
}


void HT16K33::clear()
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
    clear();


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
    I2CMasterControl::enable();


    Wire.beginTransmission(_address);

    Wire.write(0x00);


    for(uint8_t i = 0; i < BUFFER_SIZE; i++)
    {
        Wire.write(_buffer[i]);
    }


    Wire.endTransmission();


    I2CMasterControl::disable();
}