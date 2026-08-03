#pragma once

#include <Arduino.h>

#include "SegmentChain.h"

class DisplayGrid
{
public:
    DisplayGrid(SegmentChain* rows, uint8_t count);

    void clear();

    void setText(const String& text);

private:
    SegmentChain* _rows;
    uint8_t _count;

    void splitText(const String& text, String* lines);
};