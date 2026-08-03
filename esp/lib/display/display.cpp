#include "Display.h"


Display::Display()
:
_modules{
    HT16K33(0x70),
    HT16K33(0x71),
    HT16K33(0x72),
    HT16K33(0x73),

    HT16K33(0x74),
    HT16K33(0x75),
    HT16K33(0x76),
    HT16K33(0x77),

    HT16K33(0x70),
    HT16K33(0x71),
    HT16K33(0x72),
    HT16K33(0x73),

    HT16K33(0x74),
    HT16K33(0x75),
    HT16K33(0x76),
    HT16K33(0x77)
},

_rows{
    SegmentChain(&_modules[0], 4),
    SegmentChain(&_modules[4], 4),
    SegmentChain(&_modules[8], 4),
    SegmentChain(&_modules[12], 4)
},

_grid(_rows, ROWS)
{
}


void Display::begin()
{
    for (uint8_t i = 0; i < MODULE_COUNT; i++)
    {
        _modules[i].begin();
    }

    clear();
}


void Display::show(const String& text)
{
    _grid.clear();

    _grid.setText(text);
}


void Display::clear()
{
    _grid.clear();
}