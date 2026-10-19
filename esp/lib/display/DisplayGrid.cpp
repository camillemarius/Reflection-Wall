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
    constexpr uint8_t CHARS_PER_ROW = 24;

    const uint16_t length = text.length();

    uint16_t index = 0;

    for(uint8_t row = 0; row < _count; row++)
    {
        // Leerzeichen am Zeilenanfang wuerden den Text einruecken
        while(index < length && text[index] == ' ')
            index++;

        const uint16_t remaining = length - index;

        uint16_t take = remaining < CHARS_PER_ROW ? remaining : CHARS_PER_ROW;

        // Wuerde der Schnitt mitten in ein Wort fallen, bis zum
        // letzten Leerzeichen zurueckgehen. Passt ein einzelnes
        // Wort nicht in eine Zeile, wird es hart getrennt.
        if(take == CHARS_PER_ROW
           && index + take < length
           && text[index + take] != ' ')
        {
            uint16_t breakAt = take;

            while(breakAt > 0 && text[index + breakAt - 1] != ' ')
                breakAt--;

            if(breakAt > 0)
                take = breakAt;
        }

        String line = text.substring(index, index + take);

        index += take;

        while(line.length() < CHARS_PER_ROW)
            line += ' ';

        lines[row] = line;
    }
}
