#pragma once

#include <Arduino.h>

// ---------------------------------------------------------
// Warum laeuft der ESP gerade los?
// ---------------------------------------------------------
// Der Regelfall ist INT_GPIO_EXP: der Expander zieht seinen
// INT-Ausgang auf LOW, sobald sich ein Eingang aendert, und
// diese Leitung loest am ESP einen Reset aus.
//
// getReason() muss aufgerufen werden, bevor der Expander
// gelesen wird - das Lesen gibt die INT-Leitung wieder frei
// und loescht damit genau die Information, die hier
// ausgewertet wird. Die Funktion gibt selbst nichts aus,
// damit zwischen Reset und Expander-Lesevorgang moeglichst
// wenig Zeit vergeht; fuer die Ausgabe gibt es log().

class WakeupReason
{
public:
    enum class Reason
    {
        POWER_ON,           // Spannung angelegt, RTC-Speicher leer
        TIMER,              // Deep Sleep abgelaufen (GPIO16 -> RST)
        INT_HLK,
        INT_GPIO_EXP,       // Regelfall: Taster am Expander
        SHUTDOWN_BUTTON,    // externer Reset ohne anliegenden INT
        UNKNOWN
    };

    static Reason getReason();

    // Gibt den ermittelten Grund samt gemessener Pegel aus.
    // Erst nach dem Expander-Lesevorgang aufrufen.
    static void log(Reason reason);

    static const char* toString(Reason reason);
    static const char* resetReasonRaw();
};
