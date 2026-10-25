#pragma once
// Prueft das Zitat der Nacht. Reines C++, dieselbe Regel wie quote_fits auf dem Pi
// (gemeinsame Testfaelle in tests/quote_vectors.json).
#include <string>

namespace QuoteCheck
{
    constexpr std::size_t MAX_CHARS = 96;

    // 1 bis 96 Zeichen aus A-Z a-z 0-9 - . / : + * oder Leerzeichen, und der Text
    // passt in die vier Zeilen der Anzeige.
    bool acceptable(const std::string& text);
}
