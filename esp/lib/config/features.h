#pragma once

// ---------------------------------------------------------
// Bauschalter
// ---------------------------------------------------------
// Alle Schalter, die man je nach aufgebauter Hardware oder
// Betriebsart umlegt, stehen hier und nur hier. Reines C++,
// kein Arduino: auch lib/core duerfte diese Datei einbinden.

namespace Features
{
    // FRAM (MB85RC256V auf 0x50) eingebaut? Dann liegt die Zitatliste dort und eine
    // /quotes.txt im Flash wird einmal ins FRAM uebernommen. Auf false liegt die Liste
    // wie frueher in /quotes.txt im Flash.
    constexpr bool FRAM_INSTALLED = true;

    // Radar (HLK-LD2410S) angeschlossen? Ohne Radar liest GPIO13 wegen des Pull-ups
    // dauerhaft HIGH; auf false ignoriert die Firmware INT_HLK. Auf true stellen,
    // sobald der Radar angeschlossen ist.
    constexpr bool RADAR_INSTALLED = false;

    // Funkteil beim Aufwachen an? Auf false bleibt es aus (spart rund 70 mA und 200 ms
    // Bootzeit). Auf true stellen, sobald WLAN oder OTA gebraucht wird; der Wert gilt
    // erst ab dem naechsten Start, weil er im RTC-Speicher liegt.
    constexpr bool WAKE_RF_ENABLED = false;
}
