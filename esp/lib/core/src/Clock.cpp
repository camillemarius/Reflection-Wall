#include "Clock.h"

#include <cstring>

namespace Clock
{
    void reset(ClockData& c)
    {
        std::memset(&c, 0, sizeof(c));
    }

    void onBoot(ClockData& c, bool early)
    {
        // N1: die geplante Strecke zaehlt ganz; valid setzt nur ein Abgleich
        c.utc += c.plannedS;
        c.plannedS = 0;
        if (early)
        {
            c.exact = 0;
        }
    }

    void advance(ClockData& c, unsigned long elapsedMs)
    {
        const uint64_t total = static_cast<uint64_t>(c.ms) + elapsedMs;
        c.utc += static_cast<uint32_t>(total / 1000);
        c.ms = static_cast<uint16_t>(total % 1000);
    }

    void synced(ClockData& c, uint32_t ntpUtc)
    {
        c.utc = static_cast<uint32_t>(static_cast<int64_t>(ntpUtc) + c.testOffsetS);
        c.ms = 0;
        c.valid = 1;
        c.exact = 1;
        c.lastSyncUtc = c.utc;
    }

    void beforeSleep(ClockData& c, uint32_t sleepS, bool radio)
    {
        c.plannedS = sleepS;
        c.radio = radio ? 1 : 0;
    }

    bool freshSync(const ClockData& c)
    {
        return c.valid && c.exact && static_cast<uint32_t>(c.utc - c.lastSyncUtc) <= FRESH_SYNC_S;
    }
}
