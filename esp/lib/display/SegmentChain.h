#pragma once

#include <Arduino.h>

#include "HT16K33.h"

class SegmentChain
{
public:

    SegmentChain(HT16K33* modules, uint8_t count);

    void clear();

    void setText(const String& text);

private:

    HT16K33* _modules;
    uint8_t _count;

    static constexpr uint8_t CHARS_PER_MODULE = 8;
};