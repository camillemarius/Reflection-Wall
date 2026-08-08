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

private:
    static constexpr uint8_t MODULE_COUNT = 16;
    static constexpr uint8_t ROWS = 4;

    HT16K33 _modules[MODULE_COUNT];

    SegmentChain _rows[ROWS];

    DisplayGrid _grid;
};