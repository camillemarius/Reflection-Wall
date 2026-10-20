#pragma once

#include <cstddef>
#include "IQuoteStore.h"
#include "QuoteStore.h"
#include "SlotStore.h"

struct FramLoadInfo
{
    bool imported = false;       // Briefkasten uebernommen und geloescht
    bool importFailed = false;   // Briefkasten gelesen, aber Schreiben ins FRAM gescheitert
    bool busError = false;       // FRAM nicht lesbar
    std::size_t bytes = 0;       // Laenge der gelesenen oder uebernommenen Liste
};

// Liste im FRAM. Eine /quotes.txt (oder altes /text.txt) im Flash ist der Briefkasten:
// Sie wird einmal ins FRAM uebernommen und danach geloescht.
class FramQuoteStore : public IQuoteStore
{
public:
    FramQuoteStore(IByteStore& fram, IFileSystem& mailbox);

    QuoteList load() override;
    // false nach Busfehler oder gescheitertem Import dieses Durchlaufs
    bool save(const QuoteList& list) override;
    const FramLoadInfo& lastLoad() const;

private:
    // true, wenn ein Briefkasten gefunden wurde; list enthaelt dann dessen Liste
    bool readMailbox(QuoteList& list);

    SlotStore slots_;
    IFileSystem& mailbox_;
    FramLoadInfo info_;
    bool refuseSave_ = false;
};
