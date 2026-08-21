#pragma once

#include <Arduino.h>

#include "HT16K33.h"
#include "SegmentChain.h"
#include "DisplayGrid.h"

class Display
{
public:
    Display();

    void begin();

    void show(const String& text);

    void clear();

<<<<<<< HEAD
    bool testConnection(Print& output);

private:
    static constexpr uint8_t MODULE_COUNT = 12;
=======
private:
    static constexpr uint8_t MODULE_COUNT = 16;
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61
    static constexpr uint8_t ROWS = 4;

    HT16K33 _modules[MODULE_COUNT];

    SegmentChain _rows[ROWS];

    DisplayGrid _grid;
};