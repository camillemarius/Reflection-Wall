#include "TextLayout.h"

namespace TextLayout
{
    Layout wrap(const std::string& text)
    {
        Layout layout;
        const std::size_t length = text.length();
        std::size_t index = 0;

        for (std::size_t row = 0; row < ROWS; row++)
        {
            // Leerzeichen am Zeilenanfang wuerden den Text einruecken
            while (index < length && text[index] == ' ')
                index++;

            const std::size_t remaining = length - index;
            std::size_t take = remaining < CHARS_PER_ROW ? remaining : CHARS_PER_ROW;

            // Faellt der Schnitt mitten in ein Wort, bis zum letzten
            // Leerzeichen zurueckgehen. Passt ein Wort nicht in eine Zeile,
            // wird es hart getrennt.
            if (take == CHARS_PER_ROW
                && index + take < length
                && text[index + take] != ' ')
            {
                std::size_t breakAt = take;
                while (breakAt > 0 && text[index + breakAt - 1] != ' ')
                    breakAt--;
                if (breakAt > 0)
                    take = breakAt;
            }

            std::string line = text.substr(index, take);
            index += take;
            line.resize(CHARS_PER_ROW, ' ');
            layout.rows[row] = line;
        }

        while (index < length && text[index] == ' ')
            index++;
        layout.fits = (index >= length);
        return layout;
    }
}
