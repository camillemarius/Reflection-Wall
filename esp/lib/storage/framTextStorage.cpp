#include "FramTextStorage.h"


FramTextStorage::FramTextStorage(uint8_t address)
    : _address(address)
{
}


bool FramTextStorage::begin()
{
    Wire.begin();

    Wire.beginTransmission(_address);

    return Wire.endTransmission() == 0;
}


bool FramTextStorage::writeText(const String& text)
{
    uint16_t length = text.length();

    if (length > MAX_TEXT_LENGTH)
        return false;

    uint8_t lenHigh = (length >> 8) & 0xFF;
    uint8_t lenLow  = length & 0xFF;

    if (!writeByte(TEXT_ADDRESS, lenHigh))
        return false;

    if (!writeByte(TEXT_ADDRESS + 1, lenLow))
        return false;

    return writeBlock(
        TEXT_ADDRESS + 2,
        reinterpret_cast<const uint8_t*>(text.c_str()),
        length
    );
}


String FramTextStorage::readText()
{
    uint16_t length = 0;

    uint8_t lenHigh = readByte(TEXT_ADDRESS);
    uint8_t lenLow  = readByte(TEXT_ADDRESS + 1);

    length = ((uint16_t)lenHigh << 8) | lenLow;

    if (length == 0 || length > MAX_TEXT_LENGTH)
        return "";

    uint8_t buffer[MAX_TEXT_LENGTH + 1];

    if (!readBlock(TEXT_ADDRESS + 2, buffer, length))
        return "";

    buffer[length] = '\0';

    return String((char*)buffer);
}


void FramTextStorage::clear()
{
    uint8_t zero = 0;

    writeByte(TEXT_ADDRESS, zero);
    writeByte(TEXT_ADDRESS + 1, zero);
}


bool FramTextStorage::writeByte(uint16_t address, uint8_t data)
{
    Wire.beginTransmission(_address);

    Wire.write((address >> 8) & 0xFF);
    Wire.write(address & 0xFF);
    Wire.write(data);

    return Wire.endTransmission() == 0;
}


uint8_t FramTextStorage::readByte(uint16_t address)
{
    Wire.beginTransmission(_address);

    Wire.write((address >> 8) & 0xFF);
    Wire.write(address & 0xFF);

    if (Wire.endTransmission() != 0)
        return 0;

    Wire.requestFrom(_address, (uint8_t)1);

    if (Wire.available())
        return Wire.read();

    return 0;
}


bool FramTextStorage::writeBlock(
    uint16_t address,
    const uint8_t* data,
    uint16_t length
)
{
    Wire.beginTransmission(_address);

    Wire.write((address >> 8) & 0xFF);
    Wire.write(address & 0xFF);

    for (uint16_t i = 0; i < length; i++)
    {
        Wire.write(data[i]);
    }

    return Wire.endTransmission() == 0;
}


bool FramTextStorage::readBlock(
    uint16_t address,
    uint8_t* data,
    uint16_t length
)
{
    Wire.beginTransmission(_address);

    Wire.write((address >> 8) & 0xFF);
    Wire.write(address & 0xFF);

    if (Wire.endTransmission() != 0)
        return false;

    Wire.requestFrom(_address, (uint8_t)length);

    for (uint16_t i = 0; i < length; i++)
    {
        if (!Wire.available())
            return false;

        data[i] = Wire.read();
    }

    return true;
}