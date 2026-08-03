#include "EspTextStorage.h"


bool EspTextStorage::begin()
{
    return LittleFS.begin();
}


bool EspTextStorage::writeText(const String& text)
{
    File file = LittleFS.open(FILE_NAME, "w");

    if (!file)
        return false;

    file.print(text);

    file.close();

    return true;
}


String EspTextStorage::readText()
{
    File file = LittleFS.open(FILE_NAME, "r");

    if (!file)
        return "";

    String text = file.readString();

    file.close();

    return text;
}


void EspTextStorage::clear()
{
    if (LittleFS.exists(FILE_NAME))
    {
        LittleFS.remove(FILE_NAME);
    }
}