#include "QuoteCheck.h"
#include "TextLayout.h"

namespace QuoteCheck
{
    static bool allowed(char c)
    {
        if (c >= 'A' && c <= 'Z') return true;
        if (c >= 'a' && c <= 'z') return true;
        if (c >= '0' && c <= '9') return true;
        switch (c)
        {
        case '-': case '.': case '/': case ':': case '+': case '*': case ' ':
            return true;
        default:
            return false;
        }
    }

    bool acceptable(const std::string& text)
    {
        if (text.empty() || text.length() > MAX_CHARS) return false;
        for (char c : text)
            if (!allowed(c)) return false;
        return TextLayout::wrap(text).fits;
    }
}
