#include "QuoteStore.h"

// Erste Zeile ohne \r und ohne Leerzeichen am Rand
std::string firstLineTrimmed(const std::string& content)
{
    std::string line = content.substr(0, content.find('\n'));
    const char* blanks = " \t\r";
    std::size_t begin = line.find_first_not_of(blanks);
    if (begin == std::string::npos)
    {
        return "";
    }
    std::size_t end = line.find_last_not_of(blanks);
    return line.substr(begin, end - begin + 1);
}

QuoteStore::QuoteStore(IFileSystem& fs) : fs_(fs)
{
}

QuoteList QuoteStore::load()
{
    loadFailed_ = false;
    if (fs_.exists(QuotePaths::TEMP))
    {
        fs_.remove(QuotePaths::TEMP);
    }

    std::string content;
    if (fs_.exists(QuotePaths::QUOTES))
    {
        if (fs_.read(QuotePaths::QUOTES, content))
        {
            return QuoteList::parse(content);
        }
        loadFailed_ = true;
        return QuoteList();
    }

    QuoteList list;
    if (fs_.exists(QuotePaths::LEGACY) && fs_.read(QuotePaths::LEGACY, content))
    {
        std::string line = firstLineTrimmed(content);
        if (!line.empty())
        {
            list.addNewest("", line);
            if (save(list))
            {
                fs_.remove(QuotePaths::LEGACY);
            }
        }
    }
    return list;
}

bool QuoteStore::save(const QuoteList& list)
{
    if (loadFailed_)
    {
        return false;
    }
    if (!fs_.write(QuotePaths::TEMP, list.serialize()))
    {
        fs_.remove(QuotePaths::TEMP);
        return false;
    }
    if (!fs_.rename(QuotePaths::TEMP, QuotePaths::QUOTES))
    {
        fs_.remove(QuotePaths::TEMP);
        return false;
    }
    return true;
}
