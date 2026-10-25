#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>

// Auftrag der Nacht; liegt im RTC-Speicher.
enum class NightStatus : uint8_t
{
    Idle = 0,
    Wanted = 1,
    Got = 2,
    Failed = 3
};

enum class NightResult : uint8_t
{
    None = 0,
    Ok = 1,
    NoReady = 2,
    NoAnswer = 3,
    Error = 4,
    Rejected = 5,
    SessionEnded = 6,
    NoClock = 7,
    StoreFailed = 8
};

struct NightData
{
    NightStatus status;
    uint8_t attempts; // Versuche der Nacht von date
    uint8_t rejects;  // abgelehnte Zitate im laufenden Versuch
    NightResult result;
    uint8_t pendingWrite; // quote fehlt noch in der Liste (R7)
    char date[11];        // Nacht des laufenden Auftrags, "JJJJ-MM-TT"
    char doneDate[11];    // Nacht mit Zitat
    char yesterday[97];   // neuester Text der Liste (R6)
    char quote[97];
    uint8_t pad[3];
};

static_assert(sizeof(NightData) == 224, "NightData liegt im RTC-Speicher");

namespace NightJob
{
    constexpr uint8_t MAX_ATTEMPTS = 3;
    constexpr uint8_t MAX_REJECTS = 3;

    inline void reset(NightData& n)
    {
        std::memset(&n, 0, sizeof(n));
    }

    inline bool hasEnd(const char* text, std::size_t size)
    {
        return std::memchr(text, '\0', size) != nullptr;
    }

    // Bereiche der enums und Zaehler, NUL in jedem Text
    inline bool valid(const NightData& n)
    {
        return static_cast<uint8_t>(n.status) <= static_cast<uint8_t>(NightStatus::Failed) &&
               static_cast<uint8_t>(n.result) <= static_cast<uint8_t>(NightResult::StoreFailed) &&
               n.attempts <= MAX_ATTEMPTS && n.rejects <= MAX_REJECTS && n.pendingWrite <= 1 &&
               hasEnd(n.date, sizeof(n.date)) && hasEnd(n.doneDate, sizeof(n.doneDate)) &&
               hasEnd(n.yesterday, sizeof(n.yesterday)) && hasEnd(n.quote, sizeof(n.quote));
    }
}
