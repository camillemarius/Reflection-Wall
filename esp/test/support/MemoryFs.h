#pragma once

#include <map>
#include <string>
#include "QuoteStore.h"

// Dateisystem im Speicher fuer Tests; failRename simuliert einen Abbruch beim Umbenennen
class MemoryFs : public IFileSystem
{
public:
    std::map<std::string, std::string> files;
    bool failRename = false;

    bool exists(const char* path) override
    {
        return files.count(path) > 0;
    }

    bool read(const char* path, std::string& out) override
    {
        std::map<std::string, std::string>::const_iterator it = files.find(path);
        if (it == files.end())
        {
            return false;
        }
        out = it->second;
        return true;
    }

    bool write(const char* path, const std::string& content) override
    {
        files[path] = content;
        return true;
    }

    bool rename(const char* from, const char* to) override
    {
        if (failRename)
        {
            return false;
        }
        std::map<std::string, std::string>::iterator it = files.find(from);
        if (it == files.end())
        {
            return false;
        }
        files[to] = it->second;
        files.erase(from);
        return true;
    }

    bool remove(const char* path) override
    {
        return files.erase(path) > 0;
    }
};
