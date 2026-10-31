#include "WakePlan.h"

#include <cstring>
#include <string>

#include "CivilTime.h"

namespace
{
    const int WINDOW_END_HOUR = 3;

    WakeDecision act(WakeKind kind)
    {
        return WakeDecision{kind, 0, false};
    }

    // Schlafen bis target; ist das weiter als 3 h, endet die Strecke vorher und ohne Funk
    WakeDecision sleepUntil(uint32_t now, uint32_t target, bool radioAtTarget)
    {
        const uint32_t left = (target > now) ? target - now : 1;
        if (left > WakePlan::MAX_SLEEP_S)
        {
            return WakeDecision{WakeKind::Sleep, WakePlan::MAX_SLEEP_S, false};
        }
        return WakeDecision{WakeKind::Sleep, left, radioAtTarget};
    }

    bool isDate(const char* field, std::size_t size, const std::string& date)
    {
        return std::strncmp(field, date.c_str(), size) == 0;
    }
}

namespace WakePlan
{
    WakeDecision decide(const ClockData& clock, const NightData& night, bool radioOn, bool syncFailed,
                        bool earlyWake)
    {
        // R14: ohne Uhr keine Nacht, Strecken von 3 h mit Funk. Abgeglichen wird nur nach
        // einem Kaltstart oder einem Timer-Wecken (Spec 9, Entscheid B vom 2026-10-31):
        // eine Taste wartet so nicht 14 s auf das WLAN.
        if (!clock.valid)
        {
            if (radioOn && !syncFailed && !earlyWake)
            {
                return act(WakeKind::SyncNow);
            }
            return WakeDecision{WakeKind::Sleep, MAX_SLEEP_S, true};
        }

        const uint32_t now = clock.utc;
        const CivilTime::Local local = CivilTime::toZurich(now);
        const std::string today = CivilTime::date(local);
        const bool done = isDate(night.doneDate, sizeof(night.doneDate), today);
        const int attempt = isDate(night.date, sizeof(night.date), today) ? night.attempts : 0;

        if (local.hour < WINDOW_END_HOUR && !done && attempt < NightJob::MAX_ATTEMPTS)
        {
            // Versuch k um k:00; im Fruehling faellt 02:00 auf 03:00 MESZ und damit aus dem Fenster
            const uint32_t term = CivilTime::atLocalHour(local.year, local.month, local.day, attempt);
            const uint32_t windowEnd = CivilTime::atLocalHour(local.year, local.month, local.day, WINDOW_END_HOUR);
            if (term < windowEnd)
            {
                if (now < term)
                {
                    return sleepUntil(now, term, attempt == 0);
                }
                // R2: der erste Versuch braucht einen frischen Abgleich
                if (attempt == 0 && !Clock::freshSync(clock))
                {
                    if (syncFailed)
                    {
                        return act(WakeKind::StartNight); // R16: nach eigener Uhr
                    }
                    return act(radioOn ? WakeKind::SyncNow : WakeKind::RestartWithRadio);
                }
                return act(WakeKind::StartNight);
            }
        }

        // erledigt, drei Versuche oder ausserhalb des Fensters: Richtung naechstes 00:00
        return sleepUntil(now, CivilTime::nextLocalHour(now, 0), true);
    }

    void markAttempt(NightData& night, const ClockData& clock)
    {
        const CivilTime::Local local = CivilTime::toZurich(clock.utc);
        const std::string today = CivilTime::date(local);
        if (!isDate(night.date, sizeof(night.date), today))
        {
            night.status = NightStatus::Idle;
            night.attempts = 0;
            night.result = NightResult::None;
            std::strncpy(night.date, today.c_str(), sizeof(night.date) - 1);
            night.date[sizeof(night.date) - 1] = '\0';
        }

        // Termine von heute, die schon erreicht sind (nur im Fenster)
        int reached = 0;
        if (local.hour < WINDOW_END_HOUR)
        {
            for (int k = 0; k < NightJob::MAX_ATTEMPTS; ++k)
            {
                if (CivilTime::atLocalHour(local.year, local.month, local.day, k) <= clock.utc)
                {
                    ++reached;
                }
            }
        }

        int attempts = night.attempts + 1;
        if (attempts < reached)
        {
            attempts = reached;
        }
        if (attempts > NightJob::MAX_ATTEMPTS)
        {
            attempts = NightJob::MAX_ATTEMPTS;
        }
        night.attempts = static_cast<uint8_t>(attempts);
        night.rejects = 0;
    }

    bool mayStartAttempt(const NightData& night, const ClockData& clock)
    {
        const std::string today = CivilTime::date(CivilTime::toZurich(clock.utc));
        if (!isDate(night.date, sizeof(night.date), today))
        {
            return true;
        }
        return night.status == NightStatus::Idle || night.status == NightStatus::Failed;
    }

    int32_t testOffset(uint32_t ntpUtc, int32_t leadS)
    {
        const int64_t target = static_cast<int64_t>(CivilTime::nextLocalHour(ntpUtc, 0)) - leadS;
        return static_cast<int32_t>(target - static_cast<int64_t>(ntpUtc));
    }
}
