#pragma once

#include <string>
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

class QuoteStore
{
public:
    explicit QuoteStore(IFileSystem& fs);

    // Liest die Liste; steigt bei Bedarf von /text.txt um
    QuoteList load();
    // Schreibt atomar ueber eine Temp-Datei
    bool save(const QuoteList& list);

private:
    IFileSystem& fs_;
    // true, wenn /quotes.txt vorhanden, aber nicht lesbar war: save() verweigert dann
    bool loadFailed_ = false;
};
