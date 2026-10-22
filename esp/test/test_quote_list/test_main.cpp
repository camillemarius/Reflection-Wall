#include <unity.h>
#include <string>
#include "QuoteList.h"

void setUp() {}
void tearDown() {}

static std::string numbered(int count)
{
    std::string c;
    for (int i = 1; i <= count; i++)
    {
        c += "2026-01-" + std::to_string(i) + "|Text " + std::to_string(i) + "\n";
    }
    return c;
}

void test_parse_reads_entries_in_order()
{
    QuoteList l = QuoteList::parse("2026-10-19|Neu\n2026-10-18|Alt\n");
    TEST_ASSERT_EQUAL(2, l.size());
    TEST_ASSERT_EQUAL_STRING("2026-10-19", l.at(0).date.c_str());
    TEST_ASSERT_EQUAL_STRING("Alt", l.at(1).text.c_str());
}

void test_parse_strips_carriage_return()
{
    QuoteList l = QuoteList::parse("2026-10-19|Text mit CRLF\r\n");
    TEST_ASSERT_EQUAL_STRING("Text mit CRLF", l.at(0).text.c_str());
}

void test_parse_skips_invalid_lines()
{
    QuoteList l = QuoteList::parse("\n   \nohne Trenner\n2026-10-19|\n2026-10-18|Gut\n");
    TEST_ASSERT_EQUAL(1, l.size());
    TEST_ASSERT_EQUAL_STRING("Gut", l.at(0).text.c_str());
}

void test_parse_accepts_entry_without_date()
{
    QuoteList l = QuoteList::parse("|Alter Text\n");
    TEST_ASSERT_EQUAL(1, l.size());
    TEST_ASSERT_EQUAL_STRING("", l.at(0).date.c_str());
    TEST_ASSERT_EQUAL_STRING("Alter Text", l.at(0).text.c_str());
}

void test_parse_trims_date_and_text()
{
    QuoteList l = QuoteList::parse(" 2026-10-19 |\t Text mit Rand \t\n");
    TEST_ASSERT_EQUAL(1, l.size());
    TEST_ASSERT_EQUAL_STRING("2026-10-19", l.at(0).date.c_str());
    TEST_ASSERT_EQUAL_STRING("Text mit Rand", l.at(0).text.c_str());
}

void test_parse_clears_overlong_date()
{
    QuoteList l = QuoteList::parse("2026-10-19-extra|Text\n");
    TEST_ASSERT_EQUAL(1, l.size());
    TEST_ASSERT_EQUAL_STRING("", l.at(0).date.c_str());
    TEST_ASSERT_EQUAL_STRING("Text", l.at(0).text.c_str());
}

void test_parse_keeps_at_most_30()
{
    QuoteList l = QuoteList::parse(numbered(35));
    TEST_ASSERT_EQUAL(30, l.size());
    TEST_ASSERT_EQUAL_STRING("Text 30", l.at(29).text.c_str());
}

void test_serialize_roundtrip()
{
    const std::string c = "2026-10-19|A\n|B\n";
    TEST_ASSERT_EQUAL_STRING(c.c_str(), QuoteList::parse(c).serialize().c_str());
}

void test_add_newest_puts_entry_first()
{
    QuoteList l = QuoteList::parse("2026-10-19|A\n");
    l.addNewest("2026-10-20", "X");
    TEST_ASSERT_EQUAL(2, l.size());
    TEST_ASSERT_EQUAL_STRING("X", l.at(0).text.c_str());
    TEST_ASSERT_EQUAL_STRING("2026-10-20", l.at(0).date.c_str());
    TEST_ASSERT_EQUAL_STRING("A", l.at(1).text.c_str());
}

void test_add_newest_drops_oldest_beyond_30()
{
    QuoteList l = QuoteList::parse(numbered(30));
    l.addNewest("2026-10-20", "X");
    TEST_ASSERT_EQUAL(30, l.size());
    TEST_ASSERT_EQUAL_STRING("X", l.at(0).text.c_str());
    TEST_ASSERT_EQUAL_STRING("Text 29", l.at(29).text.c_str());
}

void test_next_index_wraps_to_newest()
{
    QuoteList l = QuoteList::parse("2026-01-03|C\n2026-01-02|B\n2026-01-01|A\n");
    TEST_ASSERT_EQUAL(0, l.nextIndex(2));
    TEST_ASSERT_EQUAL(1, l.nextIndex(0));
}

void test_next_index_on_empty_list_is_zero()
{
    TEST_ASSERT_EQUAL(0, QuoteList().nextIndex(5));
}

void test_resolve_index_uses_index_when_date_matches()
{
    QuoteList l = QuoteList::parse("2026-10-19|A\n2026-10-18|B\n2026-10-17|C\n");
    TEST_ASSERT_EQUAL(1, l.resolveIndex(1, "2026-10-18"));
}

void test_resolve_index_follows_date_after_insert()
{
    QuoteList l = QuoteList::parse("2026-10-19|A\n2026-10-18|B\n");
    l.addNewest("2026-10-20", "X");
    TEST_ASSERT_EQUAL(1, l.resolveIndex(0, "2026-10-19"));
}

void test_resolve_index_with_duplicate_dates_keeps_index()
{
    QuoteList l = QuoteList::parse("2026-10-19|A\n2026-10-19|B\n");
    TEST_ASSERT_EQUAL(1, l.resolveIndex(1, "2026-10-19"));
}

void test_resolve_index_unknown_date_is_zero()
{
    QuoteList l = QuoteList::parse("2026-10-19|A\n2026-10-18|B\n");
    TEST_ASSERT_EQUAL(0, l.resolveIndex(1, "2025-01-01"));
}

void test_resolve_index_on_empty_list_is_zero()
{
    TEST_ASSERT_EQUAL(0, QuoteList().resolveIndex(3, "2026-10-19"));
}

int main(int, char**)
{
    UNITY_BEGIN();
    RUN_TEST(test_parse_reads_entries_in_order);
    RUN_TEST(test_parse_strips_carriage_return);
    RUN_TEST(test_parse_skips_invalid_lines);
    RUN_TEST(test_parse_accepts_entry_without_date);
    RUN_TEST(test_parse_trims_date_and_text);
    RUN_TEST(test_parse_clears_overlong_date);
    RUN_TEST(test_parse_keeps_at_most_30);
    RUN_TEST(test_serialize_roundtrip);
    RUN_TEST(test_add_newest_puts_entry_first);
    RUN_TEST(test_add_newest_drops_oldest_beyond_30);
    RUN_TEST(test_next_index_wraps_to_newest);
    RUN_TEST(test_next_index_on_empty_list_is_zero);
    RUN_TEST(test_resolve_index_uses_index_when_date_matches);
    RUN_TEST(test_resolve_index_follows_date_after_insert);
    RUN_TEST(test_resolve_index_with_duplicate_dates_keeps_index);
    RUN_TEST(test_resolve_index_unknown_date_is_zero);
    RUN_TEST(test_resolve_index_on_empty_list_is_zero);
    return UNITY_END();
}
