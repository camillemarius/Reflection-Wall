#pragma once

#include <Arduino.h>

#include "ITextStorage.h"

#include "EspTextStorage.h"
#include "FramTextStorage.h"


// ACHTUNG: USE_FRAM_STORAGE muss 0 bleiben. Das alte Format liegt im FRAM
// ab 0x0000 und wuerde Platz A der Zitatliste ueberschreiben. Dieser alte
// Speicher wird in Teil 1 der Umsetzung ersetzt (neue Verbindung zwischen
// ESP und Pi, siehe Spezifikation Abschnitt 16).
//#define USE_FRAM_STORAGE 1
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