#include "TextStorage.h"


TextStorage::TextStorage()
{
}


bool TextStorage::begin()
{
    return _storage.begin();
}


bool TextStorage::writeText(const String& text)
{
    return _storage.writeText(text);
}


String TextStorage::readText()
{
    return _storage.readText();
}


void TextStorage::clear()
{
    _storage.clear();
}