#pragma once

#include <Arduino.h>

#include "ITextStorage.h"

#include "EspTextStorage.h"
#include "FramTextStorage.h"


#define USE_FRAM_STORAGE 1
#define USE_FRAM_STORAGE 0


class TextStorage
{
public:
    TextStorage();

    bool begin();

    bool writeText(const String& text);

    String readText();

    void clear();


private:
#if USE_FRAM_STORAGE
    FramTextStorage _storage;
#else
    EspTextStorage _storage;
#endif
};