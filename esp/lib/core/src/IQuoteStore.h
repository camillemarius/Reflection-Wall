#pragma once

#include "QuoteList.h"

// Speicher der Zitatliste; auf dem Geraet der FRAM, fuer den Umstieg das Flash-Dateisystem
class IQuoteStore
{
public:
    virtual ~IQuoteStore() = default;
    virtual QuoteList load() = 0;
    virtual bool save(const QuoteList& list) = 0;
};
