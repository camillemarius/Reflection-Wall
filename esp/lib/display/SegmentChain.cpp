#include "SegmentChain.h"

SegmentChain::SegmentChain(HT16K33* modules, uint8_t count)
{
    _modules = modules;
    _count = count;
}

void SegmentChain::clear()
{
    for(uint8_t i = 0; i < _count; i++)
        _modules[i].clear();
}


void SegmentChain::setText(const String& text)
{
    for(uint8_t i = 0; i < _count; i++)
    {
        String chunk = text.substring(i * 8, i * 8 + 8);

        while(chunk.length() < 8)
            chunk += " ";

        _modules[i].setText(chunk);
    }
}