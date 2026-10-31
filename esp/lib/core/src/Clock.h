#pragma once

#include <cstdint>

// Uhr des ESP in UTC-Sekunden seit 1970; liegt im RTC-Speicher.
// Nach N1 zaehlt jede geplante Schlafstrecke ganz, die Uhr geht hoechstens vor.
struct ClockData
{
    uint32_t utc;
    uint32_t plannedS;    // geplante Strecke des letzten Deep Sleep
    uint32_t lastSyncUtc; // utc beim letzten Abgleich
    int32_t testOffsetS;  // R4: Verschiebung des Testschalters
    uint16_t ms;          // Rest unter einer Sekunde
    uint8_t valid;        // Zeit bekannt (nur durch einen Abgleich)
    uint8_t exact;        // seit dem Abgleich nie vor der Zeit geweckt
    uint8_t radio;        // Funk beim naechsten Start
    uint8_t pad[3];
};

static_assert(sizeof(ClockData) == 24, "ClockData liegt im RTC-Speicher");

namespace Clock
{
    constexpr uint32_t FRESH_SYNC_S = 900;

    void reset(ClockData& c);
    void onBoot(ClockData& c, bool early);
    void advance(ClockData& c, unsigned long elapsedMs);
    void synced(ClockData& c, uint32_t ntpUtc);
    void beforeSleep(ClockData& c, uint32_t sleepS, bool radio);
    bool freshSync(const ClockData& c);
}
