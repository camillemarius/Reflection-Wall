#include "QuoteList.h"

constexpr std::size_t QuoteList::MAX_QUOTES;

namespace
{
bool isBlank(const std::string& s)
{
    return s.find_first_not_of(" \t") == std::string::npos;
}

// Entfernt Leerzeichen und Tabs an beiden Enden
std::string trim(const std::string& s)
{
    const std::size_t first = s.find_first_not_of(" \t");
    if (first == std::string::npos)
    {
        return std::string();
    }
    const std::size_t last = s.find_last_not_of(" \t");
    return s.substr(first, last - first + 1);
}
}

QuoteList QuoteList::parse(const std::string& content)
{
    QuoteList list;
    std::size_t start = 0;
    while (start <= content.size() && list.quotes_.size() < MAX_QUOTES)
    {
        std::size_t end = content.find('\n', start);
        if (end == std::string::npos)
        {
            end = content.size();
        }
        std::string line = content.substr(start, end - start);
        start = end + 1;

        if (!line.empty() && line.back() == '\r')
        {
            line.pop_back();
        }
        const std::size_t sep = line.find('|');
        if (sep == std::string::npos)
        {
            continue;
        }
        const std::string text = trim(line.substr(sep + 1));
        if (isBlank(text))
        {
            continue;
        }
        // Ein zu langes Datum liesse sich nicht im RTC-Speicher merken;
        // der Eintrag bleibt, aber ohne Datum
        std::string date = trim(line.substr(0, sep));
        if (date.size() > QuoteList::MAX_DATE_LENGTH)
        {
            date.clear();
        }
        list.quotes_.push_back(Quote{date, text});
    }
    return list;
}

std::string QuoteList::serialize() const
{
    std::string out;
    for (const Quote& q : quotes_)
    {
        out += q.date + "|" + q.text + "\n";
    }
    return out;
}

void QuoteList::addNewest(const std::string& date, const std::string& text)
{
    quotes_.insert(quotes_.begin(), Quote{date, text});
    if (quotes_.size() > MAX_QUOTES)
    {
        quotes_.resize(MAX_QUOTES);
    }
}

std::size_t QuoteList::size() const
{
    return quotes_.size();
}

bool QuoteList::empty() const
{
    return quotes_.empty();
}

const Quote& QuoteList::at(std::size_t index) const
{
    return quotes_[index];
}

std::size_t QuoteList::resolveIndex(std::size_t index, const std::string& date) const
{
    if (index < quotes_.size() && quotes_[index].date == date)
    {
        return index;
    }
    for (std::size_t i = 0; i < quotes_.size(); i++)
    {
        if (quotes_[i].date == date)
        {
            return i;
        }
    }
    return 0;
}

std::size_t QuoteList::nextIndex(std::size_t index) const
{
    if (quotes_.empty())
    {
        return 0;
    }
    return (index + 1) % quotes_.size();
}
