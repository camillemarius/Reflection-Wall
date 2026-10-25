#include <unity.h>

#include <cstring>
#include <string>

#include "CivilTime.h"
#include "Clock.h"
#include "NightData.h"
#include "WakePlan.h"

void setUp() {}
void tearDown() {}

namespace
{
    const char* kindName(WakeKind kind)
    {
        switch (kind)
        {
        case WakeKind::Sleep:
            return "Sleep";
        case WakeKind::SyncNow:
            return "SyncNow";
        case WakeKind::RestartWithRadio:
            return "RestartWithRadio";
        case WakeKind::StartNight:
            return "StartNight";
        }
        return "?";
    }

    uint32_t at(int year, int month, int day, int hour, int minute = 0, int second = 0)
    {
        return CivilTime::atLocalHour(year, month, day, hour) + static_cast<uint32_t>(minute * 60 + second);
    }

    // Sommernacht 2026-07-01 auf 2026-07-02
    uint32_t midnight()
    {
        return at(2026, 7, 2, 0);
    }

    std::string dateOf(uint32_t utc)
    {
        return CivilTime::date(CivilTime::toZurich(utc));
    }

    ClockData unknownClock()
    {
        ClockData c;
        std::memset(&c, 0xFF, sizeof(c));
        Clock::reset(c);
        return c;
    }

    // eben abgeglichen
    ClockData freshClock(uint32_t utc)
    {
        ClockData c = unknownClock();
        Clock::synced(c, utc);
        return c;
    }

    // genau (Timer), aber der Abgleich liegt 1 h zurueck
    ClockData staleClock(uint32_t utc)
    {
        ClockData c = freshClock(utc - 3600);
        Clock::beforeSleep(c, 3600, false);
        Clock::onBoot(c, false);
        return c;
    }

    // vor der Zeit geweckt: ungenau, obwohl der Abgleich erst 10 min alt ist
    ClockData inexactClock(uint32_t utc)
    {
        ClockData c = freshClock(utc - 600);
        Clock::beforeSleep(c, 600, false);
        Clock::onBoot(c, true);
        return c;
    }

    void setText(char* field, std::size_t size, const std::string& text)
    {
        std::strncpy(field, text.c_str(), size - 1);
        field[size - 1] = '\0';
    }

    NightData emptyNight()
    {
        NightData n;
        std::memset(&n, 0xFF, sizeof(n));
        NightJob::reset(n);
        return n;
    }

    // Nacht von utc mit gescheiterten Versuchen
    NightData triedNight(uint32_t utc, uint8_t attempts)
    {
        NightData n = emptyNight();
        setText(n.date, sizeof(n.date), dateOf(utc));
        n.attempts = attempts;
        n.status = NightStatus::Failed;
        n.result = NightResult::NoAnswer;
        return n;
    }

    // Zitat der Nacht von utc ist da
    NightData doneNight(uint32_t utc)
    {
        NightData n = emptyNight();
        setText(n.doneDate, sizeof(n.doneDate), dateOf(utc));
        return n;
    }

    WakeDecision decide(const ClockData& c, const NightData& n, bool radioOn = false, bool syncFailed = false)
    {
        return WakePlan::decide(c, n, radioOn, syncFailed);
    }
}

#define ASSERT_KIND(expected, decision) TEST_ASSERT_EQUAL_STRING(kindName(expected), kindName((decision).kind))

#define ASSERT_SLEEP(seconds, withRadio, decision)                    \
    do                                                                \
    {                                                                 \
        const WakeDecision d_ = (decision);                           \
        TEST_ASSERT_EQUAL_STRING("Sleep", kindName(d_.kind));         \
        TEST_ASSERT_EQUAL_UINT32((seconds), d_.sleepS);               \
        TEST_ASSERT_EQUAL_INT((withRadio) ? 1 : 0, d_.radio ? 1 : 0); \
    } while (0)

// --- Clock ---

void test_on_boot_adds_planned_leg()
{
    const uint32_t t = at(2026, 7, 1, 12);
    ClockData c = freshClock(t);
    Clock::beforeSleep(c, 3600, false);
    TEST_ASSERT_EQUAL_UINT32(3600, c.plannedS);
    TEST_ASSERT_EQUAL_UINT8(0, c.radio);

    Clock::onBoot(c, false);
    TEST_ASSERT_EQUAL_UINT32(t + 3600, c.utc);
    TEST_ASSERT_EQUAL_UINT32(0, c.plannedS);
    TEST_ASSERT_EQUAL_UINT8(1, c.valid);
    TEST_ASSERT_EQUAL_UINT8(1, c.exact);

    // ein zweiter Start ohne neue Strecke zaehlt nichts mehr
    Clock::onBoot(c, false);
    TEST_ASSERT_EQUAL_UINT32(t + 3600, c.utc);
}

void test_early_wake_counts_full_leg_and_marks_inexact()
{
    const uint32_t t = at(2026, 7, 1, 20);
    ClockData c = freshClock(t);
    Clock::beforeSleep(c, 10800, true);
    Clock::onBoot(c, true);
    TEST_ASSERT_EQUAL_UINT32(t + 10800, c.utc);
    TEST_ASSERT_EQUAL_UINT32(0, c.plannedS);
    TEST_ASSERT_EQUAL_UINT8(1, c.valid);
    TEST_ASSERT_EQUAL_UINT8(0, c.exact);
    TEST_ASSERT_EQUAL_UINT8(1, c.radio);
    TEST_ASSERT_FALSE(Clock::freshSync(c));

    // ein spaeteres Timer-Wecken macht sie nicht wieder genau, erst ein Abgleich
    Clock::beforeSleep(c, 60, false);
    Clock::onBoot(c, false);
    TEST_ASSERT_EQUAL_UINT8(0, c.exact);
    Clock::synced(c, t + 10860);
    TEST_ASSERT_EQUAL_UINT8(1, c.exact);
}

void test_unknown_clock_never_becomes_known_by_boot()
{
    ClockData c = unknownClock();
    TEST_ASSERT_EQUAL_UINT8(0, c.valid);
    TEST_ASSERT_EQUAL_UINT8(0, c.exact);
    TEST_ASSERT_EQUAL_UINT32(0, c.plannedS);
    TEST_ASSERT_EQUAL_INT32(0, c.testOffsetS);

    Clock::beforeSleep(c, 10800, true);
    Clock::onBoot(c, false);
    TEST_ASSERT_EQUAL_UINT8(0, c.valid);
    TEST_ASSERT_EQUAL_UINT8(0, c.exact);

    Clock::beforeSleep(c, 10800, true);
    Clock::onBoot(c, true);
    TEST_ASSERT_EQUAL_UINT8(0, c.valid);

    Clock::advance(c, 60000);
    TEST_ASSERT_EQUAL_UINT8(0, c.valid);
    TEST_ASSERT_FALSE(Clock::freshSync(c));
}

void test_advance_keeps_ms_remainder()
{
    const uint32_t t = at(2026, 7, 1, 12);
    ClockData c = freshClock(t);
    Clock::advance(c, 400);
    Clock::advance(c, 400);
    Clock::advance(c, 400);
    TEST_ASSERT_EQUAL_UINT32(t + 1, c.utc);
    TEST_ASSERT_EQUAL_UINT16(200, c.ms);

    Clock::advance(c, 1800);
    TEST_ASSERT_EQUAL_UINT32(t + 3, c.utc);
    TEST_ASSERT_EQUAL_UINT16(0, c.ms);

    // grosse Werte laufen nicht ueber
    Clock::advance(c, 4294967295ul);
    TEST_ASSERT_EQUAL_UINT32(t + 3 + 4294967u, c.utc);
    TEST_ASSERT_EQUAL_UINT16(295, c.ms);
}

void test_synced_applies_test_offset()
{
    const uint32_t ntp = at(2026, 7, 1, 21);
    // R4: Verschiebung so, dass die Uhr 23:58 zeigt
    const int32_t offset = 2 * 3600 + 58 * 60;
    ClockData c = unknownClock();
    c.testOffsetS = offset;
    Clock::advance(c, 500);
    Clock::synced(c, ntp);
    TEST_ASSERT_EQUAL_UINT32(at(2026, 7, 1, 23, 58), c.utc);
    TEST_ASSERT_EQUAL_UINT32(c.utc, c.lastSyncUtc);
    TEST_ASSERT_EQUAL_UINT16(0, c.ms);
    TEST_ASSERT_EQUAL_UINT8(1, c.valid);
    TEST_ASSERT_EQUAL_UINT8(1, c.exact);

    // jeder weitere Abgleich addiert dieselbe Verschiebung
    Clock::advance(c, 30500);
    Clock::synced(c, ntp + 30);
    TEST_ASSERT_EQUAL_UINT32(ntp + 30 + offset, c.utc);
    TEST_ASSERT_EQUAL_UINT32(c.utc, c.lastSyncUtc);
    TEST_ASSERT_EQUAL_UINT16(0, c.ms);
    TEST_ASSERT_EQUAL_INT32(offset, c.testOffsetS);

    // auch rueckwaerts
    ClockData back = unknownClock();
    back.testOffsetS = -3600;
    Clock::synced(back, ntp);
    TEST_ASSERT_EQUAL_UINT32(ntp - 3600, back.utc);
}

void test_fresh_sync_window()
{
    const uint32_t t = at(2026, 7, 1, 23, 40);
    ClockData c = freshClock(t);
    TEST_ASSERT_TRUE(Clock::freshSync(c));
    Clock::advance(c, 899000);
    TEST_ASSERT_TRUE(Clock::freshSync(c));
    Clock::advance(c, 2000);
    TEST_ASSERT_FALSE(Clock::freshSync(c));

    // Timer-Wecken: die geschlafene Strecke zaehlt mit
    ClockData timer = freshClock(t);
    Clock::beforeSleep(timer, 899, true);
    Clock::onBoot(timer, false);
    TEST_ASSERT_TRUE(Clock::freshSync(timer));
    Clock::beforeSleep(timer, 2, true);
    Clock::onBoot(timer, false);
    TEST_ASSERT_FALSE(Clock::freshSync(timer));

    // vor der Zeit geweckt: nie frisch
    ClockData early = freshClock(t);
    Clock::beforeSleep(early, 60, true);
    Clock::onBoot(early, true);
    TEST_ASSERT_FALSE(Clock::freshSync(early));

    TEST_ASSERT_FALSE(Clock::freshSync(unknownClock()));
}

// --- WakePlan ---

void test_evening_sleeps_toward_midnight_with_radio_on_last_leg()
{
    const NightData n = doneNight(at(2026, 7, 1, 0, 30));
    ASSERT_SLEEP(10800, false, decide(staleClock(at(2026, 7, 1, 18)), n));
    ASSERT_SLEEP(5400, true, decide(staleClock(at(2026, 7, 1, 22, 30)), n));
    // genau 3 h vor Mitternacht: die Strecke endet um 00:00
    ASSERT_SLEEP(10800, true, decide(staleClock(at(2026, 7, 1, 21)), n));
    // Funk in diesem Durchlauf aendert am Abend nichts
    ASSERT_SLEEP(5400, true, decide(staleClock(at(2026, 7, 1, 22, 30)), n, true, false));
    // Winter
    ASSERT_SLEEP(5400, true, decide(staleClock(at(2026, 1, 15, 22, 30)), emptyNight()));
}

void test_unknown_clock_sleeps_3h_with_radio_and_syncs_when_radio_on()
{
    ClockData c = unknownClock();
    const NightData n = emptyNight();
    ASSERT_KIND(WakeKind::SyncNow, decide(c, n, true, false));
    ASSERT_SLEEP(10800, true, decide(c, n, false, false));
    ASSERT_SLEEP(10800, true, decide(c, n, true, true));

    // steht der Zaehler zufaellig auf Mitternacht: ohne Uhr keine Nacht
    c.utc = midnight();
    ASSERT_SLEEP(10800, true, decide(c, n, false, false));
    ASSERT_SLEEP(10800, true, decide(c, n, true, true));
}

void test_midnight_without_fresh_sync_restarts_with_radio()
{
    const NightData n = doneNight(at(2026, 7, 1, 0, 30));
    ASSERT_KIND(WakeKind::RestartWithRadio, decide(staleClock(midnight()), n, false, false));
    ASSERT_KIND(WakeKind::SyncNow, decide(staleClock(midnight()), n, true, false));
    ASSERT_KIND(WakeKind::RestartWithRadio, decide(inexactClock(midnight() + 120), n, false, false));

    // nach dem Neustart mit Funk: abgleichen
    ClockData c = staleClock(midnight() + 5);
    ASSERT_KIND(WakeKind::RestartWithRadio, decide(c, n, false, false));
    Clock::beforeSleep(c, 0, true);
    Clock::onBoot(c, false);
    ASSERT_KIND(WakeKind::SyncNow, decide(c, n, c.radio != 0, false));
}

void test_failed_sync_at_midnight_runs_by_own_clock()
{
    const NightData empty = emptyNight();
    const uint32_t own = midnight() + 5;
    ASSERT_KIND(WakeKind::StartNight, decide(staleClock(own), empty, true, true));
    ASSERT_KIND(WakeKind::StartNight, decide(inexactClock(own), empty, true, true));
    // der Versuch ist gezaehlt: weiter bis 01:00, kein neuer Abgleich
    ASSERT_SLEEP(3600 - 5, false, decide(staleClock(own), triedNight(own, 1), true, true));

    // nach einem gescheiterten Abgleich nie wieder SyncNow (und kein Neustart) im selben Durchlauf
    ASSERT_SLEEP(10800, true, decide(unknownClock(), empty, true, true));
    for (uint32_t t = at(2026, 7, 1, 12); t < at(2026, 7, 3, 12); t += 300)
    {
        for (uint8_t attempts = 0; attempts <= 3; ++attempts)
        {
            const NightData n = triedNight(t, attempts);
            for (int radio = 0; radio < 2; ++radio)
            {
                const WakeKind a = decide(staleClock(t), n, radio != 0, true).kind;
                const WakeKind b = decide(inexactClock(t), n, radio != 0, true).kind;
                TEST_ASSERT_TRUE_MESSAGE(a != WakeKind::SyncNow && a != WakeKind::RestartWithRadio, kindName(a));
                TEST_ASSERT_TRUE_MESSAGE(b != WakeKind::SyncNow && b != WakeKind::RestartWithRadio, kindName(b));
            }
        }
    }
}

void test_midnight_with_fresh_sync_starts_night()
{
    const NightData n = doneNight(at(2026, 7, 1, 0, 30));
    ASSERT_KIND(WakeKind::StartNight, decide(freshClock(midnight()), n, true, false));
    ASSERT_KIND(WakeKind::StartNight, decide(freshClock(midnight() + 60), n, false, false));

    // abgeglichen um 23:50, der Timer weckt um 00:00: noch frisch, kein zweiter Abgleich
    ClockData c = freshClock(midnight() - 600);
    const WakeDecision d = decide(c, n, true, false);
    ASSERT_SLEEP(600, true, d);
    Clock::beforeSleep(c, d.sleepS, d.radio);
    Clock::onBoot(c, false);
    ASSERT_KIND(WakeKind::StartNight, decide(c, n, c.radio != 0, false));
}

void test_sync_shows_before_midnight_sleeps_rest_with_radio()
{
    const NightData n = doneNight(at(2026, 7, 1, 0, 30));
    // die eigene Uhr ging vor (N1) und meint 00:00
    ClockData c = freshClock(midnight() - 10800);
    Clock::beforeSleep(c, 10800, true);
    Clock::onBoot(c, true);
    TEST_ASSERT_EQUAL_UINT32(midnight(), c.utc);
    ASSERT_KIND(WakeKind::SyncNow, decide(c, n, true, false));

    // der Abgleich zeigt 23:40
    Clock::synced(c, midnight() - 1200);
    ASSERT_SLEEP(1200, true, decide(c, n, true, false));
}

void test_retries_at_1_and_2()
{
    const uint32_t m = midnight();
    const NightData one = triedNight(m, 1);
    ASSERT_SLEEP(2400, false, decide(staleClock(at(2026, 7, 2, 0, 20)), one));
    ASSERT_SLEEP(2400, false, decide(staleClock(at(2026, 7, 2, 0, 20)), one, true, false));
    ASSERT_KIND(WakeKind::StartNight, decide(staleClock(at(2026, 7, 2, 1)), one));
    // kein frischer Abgleich und kein Funk noetig (R2 gilt nur fuer 00:00)
    ASSERT_KIND(WakeKind::StartNight, decide(inexactClock(at(2026, 7, 2, 1, 5)), one));

    const NightData two = triedNight(m, 2);
    ASSERT_SLEEP(3000, false, decide(staleClock(at(2026, 7, 2, 1, 10)), two));
    ASSERT_KIND(WakeKind::StartNight, decide(staleClock(at(2026, 7, 2, 2)), two));
    ASSERT_KIND(WakeKind::StartNight, decide(inexactClock(at(2026, 7, 2, 2, 30)), two));
}

void test_three_attempts_then_next_night()
{
    const uint32_t m = midnight();
    const NightData n = triedNight(m, 3);
    ASSERT_SLEEP(10800, false, decide(staleClock(at(2026, 7, 2, 2, 10)), n));
    ASSERT_SLEEP(10800, false, decide(freshClock(at(2026, 7, 2, 0, 30)), n, true, false));

    // Timer-Wecken bis zur naechsten Nacht; dort zaehlen die alten Versuche nicht
    ClockData c = staleClock(at(2026, 7, 2, 2, 10));
    int syncs = 0;
    bool started = false;
    for (int i = 0; i < 20 && !started; ++i)
    {
        const WakeDecision d = decide(c, n, c.radio != 0, false);
        if (d.kind == WakeKind::Sleep)
        {
            TEST_ASSERT_TRUE(d.sleepS >= 1 && d.sleepS <= 10800);
            Clock::beforeSleep(c, d.sleepS, d.radio);
            Clock::onBoot(c, false);
        }
        else if (d.kind == WakeKind::SyncNow)
        {
            ++syncs;
            Clock::synced(c, c.utc);
        }
        else
        {
            ASSERT_KIND(WakeKind::StartNight, d);
            started = true;
        }
    }
    TEST_ASSERT_TRUE(started);
    TEST_ASSERT_EQUAL_UINT32(at(2026, 7, 3, 0), c.utc);
    TEST_ASSERT_EQUAL_INT(1, syncs);
}

void test_done_tonight_sleeps_to_next_midnight()
{
    const uint32_t m = midnight();
    const NightData n = doneNight(m);
    ASSERT_SLEEP(10800, false, decide(freshClock(m), n, true, false));
    ASSERT_SLEEP(10800, false, decide(staleClock(at(2026, 7, 2, 1)), n));
    ASSERT_SLEEP(10800, false, decide(staleClock(at(2026, 7, 2, 2, 59)), n));
    // am Abend desselben Tages: letzte Strecke bis 00:00 mit Funk
    ASSERT_SLEEP(9000, true, decide(staleClock(at(2026, 7, 2, 21, 30)), n));
    // in der naechsten Nacht fehlt das Zitat wieder
    ASSERT_KIND(WakeKind::StartNight, decide(freshClock(at(2026, 7, 3, 0)), n));
}

void test_window_closes_at_3()
{
    const uint32_t m = midnight();
    const uint32_t three = at(2026, 7, 2, 3);
    ASSERT_KIND(WakeKind::StartNight, decide(staleClock(three - 1), triedNight(m, 2)));
    ASSERT_SLEEP(10800, false, decide(staleClock(three), triedNight(m, 1)));
    ASSERT_SLEEP(10800, false, decide(staleClock(three), triedNight(m, 2)));
    // nie versucht (Uhr erst jetzt bekannt): auch dann erst die naechste Nacht
    ASSERT_SLEEP(10800, false, decide(freshClock(three), emptyNight(), true, false));
    // naechste Nacht: die Versuche von heute zaehlen nicht mehr
    ASSERT_KIND(WakeKind::StartNight, decide(freshClock(at(2026, 7, 3, 0)), triedNight(m, 2)));
}

void test_cold_boot_in_the_night_starts_at_once()
{
    const uint32_t now = at(2026, 7, 2, 1, 30);
    // Kaltstart: Uhr unbekannt, doneDate = Datum des neuesten Eintrags (gestern)
    ClockData c = unknownClock();
    NightData n = emptyNight();
    setText(n.doneDate, sizeof(n.doneDate), "2026-07-01");
    ASSERT_KIND(WakeKind::SyncNow, decide(c, n, true, false));
    Clock::synced(c, now);
    ASSERT_KIND(WakeKind::StartNight, decide(c, n, true, false));

    // Zitat dieser Nacht schon in der Liste
    setText(n.doneDate, sizeof(n.doneDate), "2026-07-02");
    ASSERT_SLEEP(10800, false, decide(c, n, true, false));
}

namespace
{
    uint32_t nextRandom(uint32_t& seed)
    {
        seed = seed * 1103515245u + 12345u;
        return seed >> 16;
    }

    // Review Focus 2: Abend mit vielen Resets. real ist die wahre Zeit.
    // Wach entscheidet der ESP jede Sekunde; Sleep heisst dann "weiter".
    void eveningWithResets(uint32_t start, uint32_t seed)
    {
        const uint32_t realMidnight = CivilTime::nextLocalHour(start, 0);
        const NightData n = doneNight(start);
        uint32_t real = start;
        ClockData c = freshClock(real);
        bool radioOn = true;
        uint32_t awake = 0;
        bool started = false;
        for (int step = 0; step < 200000 && !started; ++step)
        {
            TEST_ASSERT_TRUE_MESSAGE(c.utc >= real, "Uhr geht nach");
            const WakeDecision d = WakePlan::decide(c, n, radioOn, false);
            if (d.kind == WakeKind::StartNight)
            {
                started = true;
            }
            else if (d.kind == WakeKind::SyncNow)
            {
                TEST_ASSERT_TRUE(radioOn);
                Clock::synced(c, real);
            }
            else if (d.kind == WakeKind::RestartWithRadio)
            {
                Clock::beforeSleep(c, 0, true);
                Clock::onBoot(c, false);
                radioOn = c.radio != 0;
                awake = 0;
            }
            else if (awake > 0)
            {
                --awake;
                ++real;
                Clock::advance(c, 1000);
            }
            else
            {
                TEST_ASSERT_TRUE(d.sleepS >= 1 && d.sleepS <= 10800);
                TEST_ASSERT_TRUE_MESSAGE(real + d.sleepS <= realMidnight, "Strecke ueber das echte 00:00");
                Clock::beforeSleep(c, d.sleepS, d.radio);
                const uint32_t r = nextRandom(seed) % 100;
                const bool early = r >= 15; // meist weckt eine Taste oder das Radar
                real += early ? d.sleepS * r / 100 : d.sleepS;
                Clock::onBoot(c, early);
                radioOn = c.radio != 0;
                awake = early ? 10 + nextRandom(seed) % 600 : 0; // die Wand ist eine Weile an
            }
        }
        TEST_ASSERT_TRUE(started);
        // weder vor dem echten 00:00 noch verschlafen
        TEST_ASSERT_EQUAL_UINT32(realMidnight, real);
        TEST_ASSERT_TRUE(Clock::freshSync(c));
    }
}

void test_many_evening_resets_never_miss_midnight()
{
    const uint32_t starts[] = {
        at(2026, 7, 1, 18),     at(2026, 7, 1, 21),   at(2026, 7, 1, 22, 59), at(2026, 7, 1, 23, 58),
        at(2026, 1, 15, 19, 7), at(2026, 3, 28, 20), at(2026, 10, 24, 20),
    };
    for (const uint32_t start : starts)
    {
        for (uint32_t seed = 1; seed <= 30; ++seed)
        {
            eveningWithResets(start, seed);
        }
    }
}

void test_spring_night_has_no_2_oclock_term()
{
    const uint32_t m = at(2026, 3, 29, 0);     // 00:00 MEZ
    const uint32_t one = at(2026, 3, 29, 1);   // 01:00 MEZ
    const uint32_t three = at(2026, 3, 29, 3); // 03:00 MESZ
    TEST_ASSERT_EQUAL_UINT32(one + 3600, three);
    TEST_ASSERT_EQUAL_UINT32(three, at(2026, 3, 29, 2));

    ASSERT_KIND(WakeKind::StartNight, decide(freshClock(m), emptyNight()));
    ASSERT_SLEEP(3000, false, decide(staleClock(m + 600), triedNight(m, 1)));
    ASSERT_KIND(WakeKind::StartNight, decide(staleClock(one), triedNight(m, 1)));
    // Versuch 2 faellt auf 03:00 MESZ: Fenster zu, naechste Nacht
    ASSERT_SLEEP(10800, false, decide(staleClock(one + 600), triedNight(m, 2)));
    ASSERT_SLEEP(10800, false, decide(staleClock(three - 1), triedNight(m, 2)));
    ASSERT_SLEEP(10800, false, decide(staleClock(three), triedNight(m, 2)));
}

void test_autumn_night_uses_first_2_oclock()
{
    const uint32_t m = at(2026, 10, 25, 0);     // 00:00 MESZ
    const uint32_t two = at(2026, 10, 25, 2);   // erstes 02:00 (MESZ)
    const uint32_t three = at(2026, 10, 25, 3); // 03:00 MEZ
    TEST_ASSERT_EQUAL_UINT32(m + 7200, two);
    TEST_ASSERT_EQUAL_UINT32(two + 7200, three);

    ASSERT_SLEEP(1800, false, decide(staleClock(two - 1800), triedNight(m, 2)));
    ASSERT_KIND(WakeKind::StartNight, decide(staleClock(two), triedNight(m, 2)));
    // zweites 02:00 (MEZ): Fenster noch offen
    ASSERT_KIND(WakeKind::StartNight, decide(staleClock(two + 3600), triedNight(m, 2)));
    ASSERT_KIND(WakeKind::StartNight, decide(staleClock(three - 1), triedNight(m, 2)));
    ASSERT_SLEEP(10800, false, decide(staleClock(two + 3600), triedNight(m, 3)));
    ASSERT_SLEEP(10800, false, decide(staleClock(three), triedNight(m, 2)));
}

// --- NightData ---

void test_night_data_valid_rejects_bad_values()
{
    TEST_ASSERT_EQUAL(24, sizeof(ClockData));
    TEST_ASSERT_EQUAL(224, sizeof(NightData));

    const NightData empty = emptyNight();
    TEST_ASSERT_TRUE(NightJob::valid(empty));
    TEST_ASSERT_EQUAL_UINT8(0, static_cast<uint8_t>(empty.status));
    TEST_ASSERT_EQUAL_UINT8(0, static_cast<uint8_t>(empty.result));
    TEST_ASSERT_EQUAL_UINT8(0, empty.attempts);
    TEST_ASSERT_EQUAL_UINT8(0, empty.rejects);
    TEST_ASSERT_EQUAL_UINT8(0, empty.pendingWrite);
    TEST_ASSERT_EQUAL_STRING("", empty.date);
    TEST_ASSERT_EQUAL_STRING("", empty.doneDate);
    TEST_ASSERT_EQUAL_STRING("", empty.yesterday);
    TEST_ASSERT_EQUAL_STRING("", empty.quote);

    // die Grenzen sind gueltig
    NightData full = emptyNight();
    full.status = NightStatus::Failed;
    full.result = NightResult::StoreFailed;
    full.attempts = 3;
    full.rejects = 3;
    full.pendingWrite = 1;
    setText(full.date, sizeof(full.date), "2026-07-02");
    setText(full.doneDate, sizeof(full.doneDate), "2026-07-01");
    setText(full.yesterday, sizeof(full.yesterday), std::string(96, 'A'));
    setText(full.quote, sizeof(full.quote), std::string(96, 'B'));
    TEST_ASSERT_TRUE(NightJob::valid(full));

    NightData bad = full;
    bad.status = static_cast<NightStatus>(4);
    TEST_ASSERT_FALSE(NightJob::valid(bad));
    bad = full;
    bad.result = static_cast<NightResult>(9);
    TEST_ASSERT_FALSE(NightJob::valid(bad));
    bad = full;
    bad.attempts = 4;
    TEST_ASSERT_FALSE(NightJob::valid(bad));
    bad = full;
    bad.rejects = 4;
    TEST_ASSERT_FALSE(NightJob::valid(bad));
    bad = full;
    bad.pendingWrite = 2;
    TEST_ASSERT_FALSE(NightJob::valid(bad));
    bad = full;
    std::memset(bad.date, 'x', sizeof(bad.date));
    TEST_ASSERT_FALSE(NightJob::valid(bad));
    bad = full;
    std::memset(bad.doneDate, 'x', sizeof(bad.doneDate));
    TEST_ASSERT_FALSE(NightJob::valid(bad));
    bad = full;
    std::memset(bad.yesterday, 'x', sizeof(bad.yesterday));
    TEST_ASSERT_FALSE(NightJob::valid(bad));
    bad = full;
    std::memset(bad.quote, 'x', sizeof(bad.quote));
    TEST_ASSERT_FALSE(NightJob::valid(bad));
}

int main(int, char**)
{
    UNITY_BEGIN();
    RUN_TEST(test_on_boot_adds_planned_leg);
    RUN_TEST(test_early_wake_counts_full_leg_and_marks_inexact);
    RUN_TEST(test_unknown_clock_never_becomes_known_by_boot);
    RUN_TEST(test_advance_keeps_ms_remainder);
    RUN_TEST(test_synced_applies_test_offset);
    RUN_TEST(test_fresh_sync_window);
    RUN_TEST(test_evening_sleeps_toward_midnight_with_radio_on_last_leg);
    RUN_TEST(test_unknown_clock_sleeps_3h_with_radio_and_syncs_when_radio_on);
    RUN_TEST(test_midnight_without_fresh_sync_restarts_with_radio);
    RUN_TEST(test_failed_sync_at_midnight_runs_by_own_clock);
    RUN_TEST(test_midnight_with_fresh_sync_starts_night);
    RUN_TEST(test_sync_shows_before_midnight_sleeps_rest_with_radio);
    RUN_TEST(test_retries_at_1_and_2);
    RUN_TEST(test_three_attempts_then_next_night);
    RUN_TEST(test_done_tonight_sleeps_to_next_midnight);
    RUN_TEST(test_window_closes_at_3);
    RUN_TEST(test_cold_boot_in_the_night_starts_at_once);
    RUN_TEST(test_many_evening_resets_never_miss_midnight);
    RUN_TEST(test_spring_night_has_no_2_oclock_term);
    RUN_TEST(test_autumn_night_uses_first_2_oclock);
    RUN_TEST(test_night_data_valid_rejects_bad_values);
    return UNITY_END();
}
