#pragma once
// 16-Segment-Schrift der Anzeige. Reines C++, eine Schrift fuer ESP und Pi
// (tests/display_vectors.json).
#include <cstdint>

namespace Glyphs
{
    // 16-Segment-Muster; a-z wie A-Z; nicht darstellbar -> 0
    uint16_t segments(char c);

    // Leerzeichen, - . / : + *, 0-9, A-Z, a-z
    bool displayable(char c);
}
