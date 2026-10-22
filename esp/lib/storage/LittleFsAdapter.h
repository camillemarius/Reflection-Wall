#pragma once

#include <string>
#include "QuoteStore.h"

// Bindet die Dateisystem-Schnittstelle der Zitatliste an LittleFS
class LittleFsAdapter : public IFileSystem
{
public:
    // Bindet LittleFS ein; false, wenn das nicht gelingt
    bool begin();

    bool exists(const char* path) override;
    bool read(const char* path, std::string& out) override;
    bool write(const char* path, const std::string& content) override;
    bool rename(const char* from, const char* to) override;
    bool remove(const char* path) override;
};
