#include "DisplayGrid.h"


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
    String lines[4];

    splitText(text, lines);

    for(uint8_t i = 0; i < _count; i++)
    {
        _rows[i].setText(lines[i]);
    }
}


void DisplayGrid::splitText(const String& text, String* lines)
{
    constexpr uint8_t CHARS_PER_ROW = 32;

    uint16_t index = 0;

    for(uint8_t row = 0; row < _count; row++)
    {
        lines[row] = "";

        for(uint8_t col = 0; col < CHARS_PER_ROW; col++)
        {
            if(index < text.length())
            {
                lines[row] += text[index++];
            }
            else
            {
                lines[row] += " ";
            }
        }
    }
}