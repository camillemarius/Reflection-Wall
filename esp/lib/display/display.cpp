#include "Display.h"
#include "I2CMasterControl.h"


Display::Display()
:_modules{
    HT16K33(0x70),
    HT16K33(0x71),
    HT16K33(0x72),

    HT16K33(0x73),
    HT16K33(0x74),
    HT16K33(0x75),

    HT16K33(0x76),
    HT16K33(0x77),
    HT16K33(0x61),
    
    HT16K33(0x69),
    HT16K33(0x6a),
    HT16K33(0x6b)
},




_rows{
    SegmentChain(&_modules[0], 3),
    SegmentChain(&_modules[3], 3),
    SegmentChain(&_modules[6], 3),
    SegmentChain(&_modules[9], 3)
},

_grid(_rows, ROWS)
{
}


void Display::begin()
{
    I2CMasterControl::enable();

    for (uint8_t i = 0; i < MODULE_COUNT; i++)
    {
        _modules[i].begin();
    }

    _grid.clear();

    I2CMasterControl::disable();
}


void Display::show(const String& text)
{
    I2CMasterControl::enable();

    _grid.clear();

    _grid.setText(text);

    I2CMasterControl::disable();
}


void Display::clear()
{
    I2CMasterControl::enable();

    _grid.clear();

    I2CMasterControl::disable();
}


bool Display::testConnection(Print& output)
{
    bool allConnected = true;

    I2CMasterControl::enable();

    for (uint8_t i = 0; i < MODULE_COUNT; i++)
    {
        uint8_t error = _modules[i].testConnectionCode();
        bool connected = error == 0;

        output.print("[17] Module ");
        output.print(i);
        output.print(" @ 0x");
        output.print(_modules[i].getAddress(), HEX);
        output.print(connected ? " OK" : " ERROR code ");
        if (!connected)
            output.print(error);
        output.println();

        if (!connected)
            allConnected = false;
    }

    I2CMasterControl::disable();

    return allConnected;
}