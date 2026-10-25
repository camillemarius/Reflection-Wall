#include "DisplayGrid.h"

#include "TextLayout.h"


DisplayGrid::DisplayGrid(SegmentChain* rows, uint8_t count)
{
    _rows = rows;
    _count = count;
}


void DisplayGrid::clear()
{
    for(uint8_t i = 0; i < _count; i++)
    {
        _rows[i].clear();
    }
}


void DisplayGrid::setText(const String& text)
{
    const TextLayout::Layout layout = TextLayout::wrap(text.c_str());

    for(uint8_t i = 0; i < _count && i < TextLayout::ROWS; i++)
    {
        _rows[i].setText(String(layout.rows[i].c_str()));
    }
}
