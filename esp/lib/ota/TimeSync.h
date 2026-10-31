#pragma once

#include <Arduino.h>

// ---------------------------------------------------------
// WLAN und Uhrzeit aus dem Internet (NTP)
// ---------------------------------------------------------
// Das Funkteil ist sonst aus. sync() und portal() schalten es
// nur fuer die Dauer des Aufrufs ein und danach wieder aus.
// Die Uhr laeuft in UTC; die Ortszeit rechnet CivilTime.

class TimeSync
{
public:
    // true: der SDK-Speicher hat Zugangsdaten (SSID)
    static bool hasCredentials();

    // Verbindet mit den gespeicherten Zugangsdaten und holt die Zeit.
    // Dauert hoechstens timeoutMs (plus Abschalten). Bei Erfolg steht
    // utc fuer die Sekunden seit 1970.
    static bool sync(unsigned long timeoutMs, uint32_t& utc);

    // Konfigurationsportal (AP "ReflectionWall") fuer timeoutS Sekunden.
    // true: verbunden, die Zugangsdaten sind gespeichert.
    static bool portal(unsigned long timeoutS);
};
