#pragma once

// ---------------------------------------------------------
// Bauschalter
// ---------------------------------------------------------
// Alle Schalter, die man je nach aufgebauter Hardware oder
// Betriebsart umlegt, stehen hier und nur hier. Reines C++,
// kein Arduino: auch lib/core duerfte diese Datei einbinden.

namespace Features
{
    // true: FRAM MB85RC256V auf 0x50 ist eingebaut. Die Zitatliste liegt dann dort.
    // Eine /quotes.txt im Flash wird einmal ins FRAM uebernommen.
    // false: Die Liste liegt wie frueher in /quotes.txt im Flash.
    constexpr bool FRAM_INSTALLED = true;

    // true: Der Radar HLK-LD2410S ist angeschlossen. Erst dann wertet die Firmware INT_HLK aus.
    // false: Die Firmware ignoriert INT_HLK, denn ohne Radar liest GPIO13 wegen des Pull-ups dauerhaft HIGH.
    // Auf true stellen, sobald der Radar angeschlossen ist.
    constexpr bool RADAR_INSTALLED = false;

    // true: Das Funkteil ist beim Aufwachen an. Auf true stellen, sobald WLAN oder OTA gebraucht wird.
    // false: Es bleibt aus und spart rund 70 mA und 200 ms Bootzeit.
    // Der Wert liegt im RTC-Speicher. Darum gilt er erst ab dem naechsten Start.
    constexpr bool WAKE_RF_ENABLED = false;
}
