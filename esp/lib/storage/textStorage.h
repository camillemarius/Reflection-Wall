#pragma once

#include <Arduino.h>

#include "ITextStorage.h"

#include "EspTextStorage.h"
#include "FramTextStorage.h"


<<<<<<< HEAD
#define USE_FRAM_STORAGE 1
=======
#define USE_FRAM_STORAGE 0
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61


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