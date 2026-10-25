#pragma once
// Zeilenumbruch der Anzeige. Reines C++, eine Regel fuer ESP und Pi
// (tests/display_vectors.json).
#include <cstddef>
#include <string>

namespace TextLayout
{
    constexpr std::size_t CHARS_PER_ROW = 24;
    constexpr std::size_t ROWS = 4;

    struct Layout
    {
        std::string rows[ROWS];   // je genau CHARS_PER_ROW Zeichen, rechts mit Leerzeichen aufgefuellt
        bool fits = true;         // der ganze Text steht in den vier Zeilen
    };

    // Leerzeichen am Zeilenanfang entfallen. Der Umbruch liegt an Wortgrenzen;
    // ein Wort, das nicht in eine Zeile passt, wird hart getrennt.
    Layout wrap(const std::string& text);
}
