#pragma once

#include <cstdint>
#include <string>

// Ortszeit Zuerich aus UTC-Sekunden seit 1970, ohne libc-Zeitfunktionen.
// MEZ = UTC+1, MESZ = UTC+2 von letztem Sonntag Maerz 01:00 UTC bis
// letztem Sonntag Oktober 01:00 UTC. Eingaben sind gueltig (Vertrag).
namespace CivilTime
{
    struct Local
    {
        int year;
        int month;
        int day;
        int hour;
        int minute;
        int second;
        bool summer;
    };

    Local toZurich(uint32_t utc);
    bool isSummer(uint32_t utc);

    // Erster Zeitpunkt (UTC) am Ortsdatum, an dem die Ortszeit hour:00 ist.
    // Fehlt hour:00 (Fruehling 02:00), gilt der erste gueltige Zeitpunkt danach (03:00 MESZ).
    // Gibt es hour:00 zweimal (Herbst 02:00), gilt das erste Mal.
    uint32_t atLocalHour(int year, int month, int day, int hour);

    // Kleinster Zeitpunkt > utc mit Ortszeit hour:00 (Regeln wie atLocalHour)
    uint32_t nextLocalHour(uint32_t utc, int hour);

    // "JJJJ-MM-TT"
    std::string date(const Local& t);
}
