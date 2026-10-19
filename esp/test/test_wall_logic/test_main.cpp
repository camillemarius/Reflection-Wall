#include <unity.h>
#include "WallLogic.h"
#include "QuoteList.h"

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

void test_stays_on_while_radar_high_without_button1()
{
    TEST_ASSERT_FALSE(wallShouldTurnOff(true, false, 0));
}

static QuoteList three()
{
    return QuoteList::parse("2026-10-19|A\n2026-10-18|B\n2026-10-17|C\n");
}

void test_select_empty_list_gives_zero()
{
    QuoteList l;
    TEST_ASSERT_EQUAL(0, selectIndex(l, WallAction::ShowNext, 5, "x"));
    TEST_ASSERT_EQUAL(0, selectIndex(l, WallAction::ShowCurrent, 5, "x"));
}

void test_select_newest_is_zero()
{
    TEST_ASSERT_EQUAL(0, selectIndex(three(), WallAction::ShowNewest, 2, "2026-10-17"));
}

void test_select_current_finds_shown_entry()
{
    TEST_ASSERT_EQUAL(1, selectIndex(three(), WallAction::ShowCurrent, 1, "2026-10-18"));
}

void test_select_none_resolves_like_current()
{
    TEST_ASSERT_EQUAL(1, selectIndex(three(), WallAction::None, 1, "2026-10-18"));
}

void test_select_next_wraps_around()
{
    TEST_ASSERT_EQUAL(0, selectIndex(three(), WallAction::ShowNext, 2, "2026-10-17"));
    TEST_ASSERT_EQUAL(2, selectIndex(three(), WallAction::ShowNext, 1, "2026-10-18"));
}

void test_select_current_after_list_shift()
{
    // Ein neuer Eintrag hat die Liste verschoben: B steht nun auf 2
    QuoteList l = QuoteList::parse("2026-10-20|N\n2026-10-19|A\n2026-10-18|B\n");
    TEST_ASSERT_EQUAL(2, selectIndex(l, WallAction::ShowCurrent, 1, "2026-10-18"));
}

void test_select_next_after_list_shift()
{
    QuoteList l = QuoteList::parse("2026-10-20|N\n2026-10-19|A\n2026-10-18|B\n");
    // Gezeigt wurde A (alter Index 0): nach dem Verschieben folgt B
    TEST_ASSERT_EQUAL(2, selectIndex(l, WallAction::ShowNext, 0, "2026-10-19"));
}

void test_select_interrupted_write_repeats_target()
{
    // Unterbrochener Schreibvorgang: gespeichert ist das Ziel (B)
    TEST_ASSERT_EQUAL(1, selectIndex(three(), WallAction::ShowCurrent, 1, "2026-10-18"));
}

void test_select_entry_without_date_uses_index()
{
    QuoteList l = QuoteList::parse("|X\n|Y\n");
    TEST_ASSERT_EQUAL(1, selectIndex(l, WallAction::ShowCurrent, 1, ""));
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
    RUN_TEST(test_stays_on_while_radar_high_without_button1);
    RUN_TEST(test_select_empty_list_gives_zero);
    RUN_TEST(test_select_newest_is_zero);
    RUN_TEST(test_select_current_finds_shown_entry);
    RUN_TEST(test_select_none_resolves_like_current);
    RUN_TEST(test_select_next_wraps_around);
    RUN_TEST(test_select_current_after_list_shift);
    RUN_TEST(test_select_next_after_list_shift);
    RUN_TEST(test_select_interrupted_write_repeats_target);
    RUN_TEST(test_select_entry_without_date_uses_index);
    return UNITY_END();
}
