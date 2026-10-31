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

    // radioOn: dieser Durchlauf hat Funk; syncFailed: ein Abgleich in diesem Durchlauf ist gescheitert;
    // earlyWake: der Durchlauf begann vor der Zeit (Taste, Reset), weder mit dem Timer noch als Kaltstart
    WakeDecision decide(const ClockData& clock, const NightData& night, bool radioOn, bool syncFailed,
                        bool earlyWake);

    // Beim Start eines Versuchs: neue Nacht -> Status, Versuche, rejects, result neu, date = heute
    // (doneDate, yesterday, quote, pendingWrite bleiben). Ein spaeter Versuch verbraucht
    // die Termine, die schon vorbei sind (Abschnitt 9, "Kaltstart in der Nacht").
    void markAttempt(NightData& night, const ClockData& clock);

    // Darf auf StartNight ein neuer Versuch beginnen? Ja in einer neuen Nacht (date ist
    // nicht heute) und nach Idle oder Failed. Laeuft GET (Wanted) oder ist das Zitat da
    // (Got), nein: decide beachtet den Status nicht, markAttempt zaehlte einen Termin zu viel.
    bool mayStartAttempt(const NightData& night, const ClockData& clock);

    // R4 (NIGHT_TEST): Verschiebung der Uhr, mit der leadS Sekunden nach ntpUtc
    // Mitternacht (Ortszeit) ist. Ein negatives leadS heisst: Mitternacht war vor -leadS
    // Sekunden (-5400: die Uhr zeigt 01:30). Die Application legt sie beim ersten Abgleich
    // nach einem Kaltstart fest; jeder spaetere Abgleich nimmt dieselbe (Clock::synced).
    int32_t testOffset(uint32_t ntpUtc, int32_t leadS);
}
