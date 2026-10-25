#pragma once

#include <cstdint>

#include "Clock.h"
#include "NightData.h"

// Weckplan: Termine 00:00, 01:00, 02:00 Ortszeit, Fenster bis 03:00,
// hoechstens 3 h am Stueck. Reine Logik ohne Arduino-Abhaengigkeit.
enum class WakeKind
{
    Sleep,
    SyncNow,
    RestartWithRadio,
    StartNight
};

struct WakeDecision
{
    WakeKind kind;
    uint32_t sleepS; // nur Sleep: 1 bis MAX_SLEEP_S
    bool radio;      // nur Sleep: Funk beim naechsten Start
};

namespace WakePlan
{
    constexpr uint32_t MAX_SLEEP_S = 10800;

    // radioOn: dieser Durchlauf hat Funk; syncFailed: ein Abgleich in diesem Durchlauf ist gescheitert
    WakeDecision decide(const ClockData& clock, const NightData& night, bool radioOn, bool syncFailed);
}
