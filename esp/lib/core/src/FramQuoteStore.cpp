#include "FramQuoteStore.h"

FramQuoteStore::FramQuoteStore(IByteStore& fram, IFileSystem& mailbox)
    : slots_(fram), mailbox_(mailbox)
{
}

bool FramQuoteStore::readMailbox(QuoteList& list)
{
    std::string content;
    if (mailbox_.exists(QuotePaths::QUOTES))
    {
        // Nicht lesbar: weder importieren noch loeschen, das FRAM gilt
        if (!mailbox_.read(QuotePaths::QUOTES, content))
        {
            return false;
        }
        list = QuoteList::parse(content);
        return true;
    }
    if (mailbox_.exists(QuotePaths::LEGACY) && mailbox_.read(QuotePaths::LEGACY, content))
    {
        std::string line = firstLineTrimmed(content);
        if (!line.empty())
        {
            list.addNewest("", line);
            return true;
        }
    }
    return false;
}

QuoteList FramQuoteStore::load()
{
    info_ = FramLoadInfo();
    refuseSave_ = false;

    QuoteList list;
    if (readMailbox(list))
    {
        const std::string serialized = list.serialize();
        info_.bytes = serialized.size();
        if (!slots_.write(serialized))
        {
            info_.importFailed = true;
            refuseSave_ = true;
            return list;
        }
        // Der Briefkasten ersetzt auch ein altes /text.txt, sonst wuerde es beim naechsten
        // Start ueber die neue Liste importiert. Ergebnisse egal: Eine uebrig gebliebene
        // Datei wird beim naechsten Start noch einmal mit demselben Ergebnis uebernommen.
        mailbox_.remove(QuotePaths::QUOTES);
        mailbox_.remove(QuotePaths::LEGACY);
        mailbox_.remove(QuotePaths::TEMP);
        info_.imported = true;
        return list;
    }

    std::string content;
    switch (slots_.read(content))
    {
    case SlotStore::ReadResult::Ok:
        info_.bytes = content.size();
        return QuoteList::parse(content);
    case SlotStore::ReadResult::Empty:
        return QuoteList();
    case SlotStore::ReadResult::BusError:
    default:
        info_.busError = true;
        refuseSave_ = true;
        return QuoteList();
    }
}

bool FramQuoteStore::save(const QuoteList& list)
{
    if (refuseSave_)
    {
        return false;
    }
    return slots_.write(list.serialize());
}

const FramLoadInfo& FramQuoteStore::lastLoad() const
{
    return info_;
}
