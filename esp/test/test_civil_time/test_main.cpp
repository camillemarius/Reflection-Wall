#include <unity.h>
#include "CivilTime.h"

void setUp() {}
void tearDown() {}

static void assertLocal(const CivilTime::Local& t, int y, int mo, int d, int h, int mi, int s, bool summer)
{
    TEST_ASSERT_EQUAL(y, t.year);
    TEST_ASSERT_EQUAL(mo, t.month);
    TEST_ASSERT_EQUAL(d, t.day);
    TEST_ASSERT_EQUAL(h, t.hour);
    TEST_ASSERT_EQUAL(mi, t.minute);
    TEST_ASSERT_EQUAL(s, t.second);
    TEST_ASSERT_EQUAL(summer, t.summer);
}

void test_winter_is_utc_plus_1()
{
    // 2026-01-15 12:00:00 UTC
    assertLocal(CivilTime::toZurich(1768478400u), 2026, 1, 15, 13, 0, 0, false);
}

void test_summer_is_utc_plus_2()
{
    // 2026-07-01 22:30:00 UTC
    assertLocal(CivilTime::toZurich(1782945000u), 2026, 7, 2, 0, 30, 0, true);
}

void test_spring_change()
{
    // 2026-03-29 00:59:59 UTC und 01:00:00 UTC
    assertLocal(CivilTime::toZurich(1774745999u), 2026, 3, 29, 1, 59, 59, false);
    assertLocal(CivilTime::toZurich(1774746000u), 2026, 3, 29, 3, 0, 0, true);
    TEST_ASSERT_FALSE(CivilTime::isSummer(1774745999u));
    TEST_ASSERT_TRUE(CivilTime::isSummer(1774746000u));
}

void test_autumn_change()
{
    // 2026-10-25 00:59:59 UTC und 01:00:00 UTC
    assertLocal(CivilTime::toZurich(1792889999u), 2026, 10, 25, 2, 59, 59, true);
    assertLocal(CivilTime::toZurich(1792890000u), 2026, 10, 25, 2, 0, 0, false);
    TEST_ASSERT_TRUE(CivilTime::isSummer(1792889999u));
    TEST_ASSERT_FALSE(CivilTime::isSummer(1792890000u));
}

void test_leap_day()
{
    // 2028-02-29 12:00 UTC, 2028-03-01 00:00 UTC
    assertLocal(CivilTime::toZurich(1835438400u), 2028, 2, 29, 13, 0, 0, false);
    assertLocal(CivilTime::toZurich(1835481600u), 2028, 3, 1, 1, 0, 0, false);
    // 2100 ist kein Schaltjahr: 2100-02-28 23:59:59 UTC, 2100-03-01 00:00:00 UTC
    assertLocal(CivilTime::toZurich(4107542399u), 2100, 3, 1, 0, 59, 59, false);
    assertLocal(CivilTime::toZurich(4107542400u), 2100, 3, 1, 1, 0, 0, false);
}

void test_at_local_hour_midnight()
{
    // 2026-07-02 00:00 MESZ = 2026-07-01 22:00 UTC
    TEST_ASSERT_EQUAL_UINT32(1782943200u, CivilTime::atLocalHour(2026, 7, 2, 0));
}

void test_at_local_hour_spring_gap()
{
    // 02:00 gibt es nicht; 03:00 MESZ = 01:00 UTC
    TEST_ASSERT_EQUAL_UINT32(1774746000u, CivilTime::atLocalHour(2026, 3, 29, 2));
    // 00:00 und 01:00 liegen davor, in MEZ
    TEST_ASSERT_EQUAL_UINT32(1774742400u - 3600u, CivilTime::atLocalHour(2026, 3, 29, 0));
    TEST_ASSERT_EQUAL_UINT32(1774742400u, CivilTime::atLocalHour(2026, 3, 29, 1));
}

void test_at_local_hour_autumn_twice()
{
    // erstes 02:00 (MESZ) = 2026-10-25 00:00 UTC
    TEST_ASSERT_EQUAL_UINT32(1792886400u, CivilTime::atLocalHour(2026, 10, 25, 2));
}

void test_next_local_hour()
{
    // genau 00:00 -> naechster Tag
    TEST_ASSERT_EQUAL_UINT32(1768604400u, CivilTime::nextLocalHour(1768518000u, 0));
    // 23:59:59 Ortszeit (22:59:59 UTC) -> 00:00 am naechsten Tag
    TEST_ASSERT_EQUAL_UINT32(1768518000u, CivilTime::nextLocalHour(1768517999u, 0));
}

void test_next_local_hour_changes()
{
    // Fruehling: vor dem Wechsel -> 03:00 MESZ; ab dann -> naechster Tag 02:00 MESZ
    TEST_ASSERT_EQUAL_UINT32(1774746000u, CivilTime::nextLocalHour(1774744200u, 2));
    TEST_ASSERT_EQUAL_UINT32(1774828800u, CivilTime::nextLocalHour(1774746000u, 2));
    // Herbst: erstes 02:00; danach das 02:00 des naechsten Tages (MEZ)
    TEST_ASSERT_EQUAL_UINT32(1792886400u, CivilTime::nextLocalHour(1792880000u, 2));
    TEST_ASSERT_EQUAL_UINT32(1792976400u, CivilTime::nextLocalHour(1792886400u, 2));
}

void test_date_string()
{
    // 2026-03-09 10:00 UTC
    TEST_ASSERT_EQUAL_STRING("2026-03-09", CivilTime::date(CivilTime::toZurich(1773050400u)).c_str());
}

int main(int, char**)
{
    UNITY_BEGIN();
    RUN_TEST(test_winter_is_utc_plus_1);
    RUN_TEST(test_summer_is_utc_plus_2);
    RUN_TEST(test_spring_change);
    RUN_TEST(test_autumn_change);
    RUN_TEST(test_leap_day);
    RUN_TEST(test_at_local_hour_midnight);
    RUN_TEST(test_at_local_hour_spring_gap);
    RUN_TEST(test_at_local_hour_autumn_twice);
    RUN_TEST(test_next_local_hour);
    RUN_TEST(test_next_local_hour_changes);
    RUN_TEST(test_date_string);
    return UNITY_END();
}
