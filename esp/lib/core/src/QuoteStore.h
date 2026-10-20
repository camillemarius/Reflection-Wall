#pragma once

#include <string>
#include "IQuoteStore.h"
#include "QuoteList.h"

namespace QuotePaths
{
    constexpr char QUOTES[] = "/quotes.txt";
    constexpr char TEMP[] = "/quotes.new";
    constexpr char LEGACY[] = "/text.txt";
}

// Schmale Dateisystem-Schnittstelle; auf dem Geraet an LittleFS gebunden
class IFileSystem
{
public:
    virtual ~IFileSystem() = default;
    virtual bool exists(const char* path) = 0;
    virtual bool read(const char* path, std::string& out) = 0;
    virtual bool write(const char* path, const std::string& content) = 0;
    // ersetzt ein vorhandenes Ziel
    virtual bool rename(const char* from, const char* to) = 0;
    virtual bool remove(const char* path) = 0;
};

// Erste Zeile ohne Zeilenende-Zeichen und ohne Leerzeichen am Rand; gemeinsam fuer Flash- und FRAM-Speicher
std::string firstLineTrimmed(const std::string& content);

class QuoteStore : public IQuoteStore
{
public:
    explicit QuoteStore(IFileSystem& fs);

    // Liest die Liste; steigt bei Bedarf von /text.txt um
    QuoteList load() override;
    // Schreibt atomar ueber eine Temp-Datei
    bool save(const QuoteList& list) override;

private:
    IFileSystem& fs_;
    // true, wenn /quotes.txt vorhanden, aber nicht lesbar war: save() verweigert dann
    bool loadFailed_ = false;
};
