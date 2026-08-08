#include "PCF8575.h"


PCF8575::PCF8575(uint8_t address)
{
    _address = address;
    _state = 0xFFFF;
}


bool PCF8575::begin()
{
    Wire.begin();

    return true;
}


bool PCF8575::write16(uint16_t value)
{
    Wire.beginTransmission(_address);

    Wire.write(value & 0xFF);
    Wire.write((value >> 8) & 0xFF);

    return Wire.endTransmission() == 0;
}


uint16_t PCF8575::read16()
{
    Wire.requestFrom(_address, (uint8_t)2);

    if(Wire.available() < 2)
        return 0xFFFF;


    uint8_t low = Wire.read();
    uint8_t high = Wire.read();

    _state = (high << 8) | low;

    return _state;
}


bool PCF8575::digitalWrite(uint8_t pin, bool state)
{
    if(pin > 15)
        return false;


    if(state)
        _state |= (1 << pin);
    else
        _state &= ~(1 << pin);


    return write16(_state);
}


bool PCF8575::digitalRead(uint8_t pin)
{
    if(pin > 15)
        return false;


    uint16_t value = read16();

    return value & (1 << pin);
}


void PCF8575::setOutput(uint8_t pin, bool state)
{
    digitalWrite(pin, state);
}


void PCF8575::clear()
{
    _state = 0xFFFF;
    write16(_state);
}