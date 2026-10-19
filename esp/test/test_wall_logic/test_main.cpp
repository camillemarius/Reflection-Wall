#include <unity.h>
#include "WallLogic.h"

void setUp() {}
void tearDown() {}

void test_button1_on_dark_wall_shows_newest()
{
    WallBoot b = {false, false, false, true};
    TEST_ASSERT_EQUAL(WallAction::ShowNewest, decideOnBoot(b));
}

void test_button1_on_lit_wall_shows_next()
{
    WallBoot b = {true, false, true, true};
    TEST_ASSERT_EQUAL(WallAction::ShowNext, decideOnBoot(b));
}

void test_radar_on_dark_wall_shows_newest()
{
    WallBoot b = {false, false, true, false};
    TEST_ASSERT_EQUAL(WallAction::ShowNewest, decideOnBoot(b));
}

void test_radar_on_lit_wall_does_nothing()
{
    WallBoot b = {true, false, true, false};
    TEST_ASSERT_EQUAL(WallAction::None, decideOnBoot(b));
}

void test_interrupted_write_shows_current_again()
{
    WallBoot b = {true, true, false, false};
    TEST_ASSERT_EQUAL(WallAction::ShowCurrent, decideOnBoot(b));
}

void test_button1_wins_over_interrupted_write()
{
    WallBoot b = {true, true, false, true};
    TEST_ASSERT_EQUAL(WallAction::ShowNext, decideOnBoot(b));
}

void test_nothing_happens_on_dark_wall_without_cause()
{
    WallBoot b = {false, false, false, false};
    TEST_ASSERT_EQUAL(WallAction::None, decideOnBoot(b));
}

void test_stays_on_while_radar_high()
{
    TEST_ASSERT_FALSE(wallShouldTurnOff(true, true, 120000));
}

void test_stays_on_during_button1_minute()
{
    TEST_ASSERT_FALSE(wallShouldTurnOff(false, true, 59999));
}

void test_turns_off_after_button1_minute()
{
    TEST_ASSERT_TRUE(wallShouldTurnOff(false, true, 60000));
}

void test_turns_off_when_radar_low_without_button1()
{
    TEST_ASSERT_TRUE(wallShouldTurnOff(false, false, 0));
}

int main(int, char **)
{
    UNITY_BEGIN();
    RUN_TEST(test_button1_on_dark_wall_shows_newest);
    RUN_TEST(test_button1_on_lit_wall_shows_next);
    RUN_TEST(test_radar_on_dark_wall_shows_newest);
    RUN_TEST(test_radar_on_lit_wall_does_nothing);
    RUN_TEST(test_interrupted_write_shows_current_again);
    RUN_TEST(test_button1_wins_over_interrupted_write);
    RUN_TEST(test_nothing_happens_on_dark_wall_without_cause);
    RUN_TEST(test_stays_on_while_radar_high);
    RUN_TEST(test_stays_on_during_button1_minute);
    RUN_TEST(test_turns_off_after_button1_minute);
    RUN_TEST(test_turns_off_when_radar_low_without_button1);
    return UNITY_END();
}
