#include "LittleFsAdapter.h"

#include <Arduino.h>
#include <LittleFS.h>

bool LittleFsAdapter::begin()
{
    return LittleFS.begin();
}

bool LittleFsAdapter::exists(const char* path)
{
    return LittleFS.exists(path);
}

bool LittleFsAdapter::read(const char* path, std::string& out)
{
    File file = LittleFS.open(path, "r");

    if (!file)
        return false;

    const String content = file.readString();
    file.close();

    out.assign(content.c_str(), content.length());

    return true;
}

bool LittleFsAdapter::write(const char* path, const std::string& content)
{
    File file = LittleFS.open(path, "w");

    if (!file)
        return false;

    const size_t written = file.write(
        reinterpret_cast<const uint8_t*>(content.data()), content.size());
    file.close();

    return written == content.size();
}

bool LittleFsAdapter::rename(const char* from, const char* to)
{
    return LittleFS.rename(from, to);
}

bool LittleFsAdapter::remove(const char* path)
{
    return LittleFS.remove(path);
}
