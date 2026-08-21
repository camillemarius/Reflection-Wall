#include "HT16K33.h"

#include "ASCII16Seg.h"
#include "I2CMasterControl.h"
<<<<<<< HEAD
#include "pinMapping.h"
=======
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61


HT16K33::HT16K33(uint8_t address)
{
    _address = address;
<<<<<<< HEAD
    clearBuffer();
=======
    clear();
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61
}


void HT16K33::begin()
{
<<<<<<< HEAD
    Wire.begin(Pins::I2C_SDA, Pins::I2C_SCL);
    Wire.setClock(50000);

    init();

=======
    Wire.begin();

    init();
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61
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


<<<<<<< HEAD
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
=======
void HT16K33::clear()
{
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61
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
<<<<<<< HEAD
    clearBuffer();
=======
    clear();
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61


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
<<<<<<< HEAD
=======
    I2CMasterControl::enable();


>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61
    Wire.beginTransmission(_address);

    Wire.write(0x00);


    for(uint8_t i = 0; i < BUFFER_SIZE; i++)
    {
        Wire.write(_buffer[i]);
    }


    Wire.endTransmission();


<<<<<<< HEAD
=======
    I2CMasterControl::disable();
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61
}