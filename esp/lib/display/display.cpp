#include "Display.h"
#include "I2CMasterControl.h"
#include "DebugLogger.h"
#include <Wire.h>
#include "pinMapping.h"

Display::Display()
:_modules{
    HT16K33(0x70),
    HT16K33(0x71),
    HT16K33(0x72),

    HT16K33(0x73),
    HT16K33(0x74),
    HT16K33(0x75),

    HT16K33(0x76),
    HT16K33(0x77),

    // 0x70-0x77 sind mit den HT16K33-Jumpern ausgeschoepft.
    // Beide LTC4316 uebersetzen mit 0x08 (XORH an GND, XORL
    // 1000).
    //
    // Hinter den LTC4316 nur native Adressen mit A0 = 1: Module
    // mit A0 = 0 (nativ 0x70, 0x72) quittierten dort Bytes mit
    // Bit 0 = 1 nicht zuverlaessig (NACK, teils falsche Inhalte).
    // Nachgewiesen durch Jumper- und Board-Tausch: der Fehler
    // haengt an A0 = 0 hinter dem Translator, nicht am Board.
    //
    // Zeile 3, Spalte 3: erster LTC4316, Modul nativ 0x77.
    HT16K33(0x7f),

    // Zeile 4: zweiter LTC4316, Module nativ 0x71/0x73/0x75.
    HT16K33(0x79),
    HT16K33(0x7b),
    HT16K33(0x7d)
},
_rows{
    SegmentChain(&_modules[0], 3),
    SegmentChain(&_modules[3], 3),
    SegmentChain(&_modules[6], 3),
    SegmentChain(&_modules[9], 3)
},
_grid(_rows, ROWS)
{
}

void Display::begin()
{
    I2CMasterControl::enable();

    for (uint8_t i = 0; i < MODULE_COUNT; i++)
        _modules[i].begin();

    // Eine Sammelmeldung statt einer Zeile pro Modul
    uint8_t failed = 0;
    uint8_t firstError = 0;
    char addresses[MODULE_COUNT * 5 + 1];
    size_t offset = 0;

    for (uint8_t i = 0; i < MODULE_COUNT; i++)
    {
        uint8_t error = _modules[i].testConnectionCode();

        if (error == 0)
            continue;

        if (failed == 0)
            firstError = error;

        failed++;

        if (offset + 5 < sizeof(addresses))
            offset += snprintf(addresses + offset,
                               sizeof(addresses) - offset,
                               "%s0x%02X",
                               offset ? " " : "",
                               _modules[i].getAddress());
    }

    addresses[offset] = '\0';

    if (failed == 0)
        DebugSerial.printf("[DISPLAY] Alle %d Module OK\n", MODULE_COUNT);
    else if (failed == MODULE_COUNT)
        DebugSerial.printf("[DISPLAY] FEHLER: kein Modul antwortet (%d/%d, ERROR=%d)\n",
                           failed, MODULE_COUNT, firstError);
    else
        DebugSerial.printf("[DISPLAY] FEHLER: %d/%d Module ohne Antwort: %s (ERROR=%d)\n",
                           failed, MODULE_COUNT, addresses, firstError);

    I2CMasterControl::disable();
}

void Display::show(const String& text)
{
    I2CMasterControl::enable();

    for (uint8_t i = 0; i < MODULE_COUNT; i++)
        _modules[i].resetWriteStats();

    _grid.clear();
    _grid.setText(text);

    I2CMasterControl::disable();

    // Ohne diese Meldung bleibt ein abgebrochener Zugriff
    // unbemerkt - das Modul zeigt dann nur die ersten Zeichen.
    for (uint8_t i = 0; i < MODULE_COUNT; i++)
    {
        const uint8_t error = _modules[i].lastWriteError();
        const uint8_t retries = _modules[i].writeRetries();

        if (error != 0)
            DebugSerial.printf("[DISPLAY] FEHLER: Modul 0x%02X nicht beschrieben (ERROR=%u, %u Wiederholungen)\n",
                               _modules[i].getAddress(), error, retries);
        else if (retries != 0)
            DebugSerial.printf("[DISPLAY] Modul 0x%02X erst nach %u Wiederholung(en) beschrieben\n",
                               _modules[i].getAddress(), retries);
    }
}

void Display::clear()
{
    I2CMasterControl::enable();

    _grid.clear();

    I2CMasterControl::disable();
}

void Display::setPower(bool on)
{
    I2CMasterControl::enable();

    for (uint8_t i = 0; i < MODULE_COUNT; i++)
        _modules[i].setDisplayOn(on);

    I2CMasterControl::disable();
}

bool Display::testConnection(Print& output)
{
    bool allConnected = true;

    I2CMasterControl::enable();

    for (uint8_t i = 0; i < MODULE_COUNT; i++)
    {
        uint8_t error = _modules[i].testConnectionCode();

        if (error != 0)
        {
            output.printf("[DISPLAY] Module 0x%02X ERROR=%d\n", _modules[i].getAddress(), error);
            allConnected = false;
        }
    }

    I2CMasterControl::disable();

    return allConnected;
}