#include <unity.h>
#include <string>
#include "QuoteStore.h"
#include "../support/MemoryFs.h"

void setUp() {}
void tearDown() {}

void test_load_without_files_is_empty()
{
    MemoryFs fs;
    TEST_ASSERT_TRUE(QuoteStore(fs).load().empty());
}

void test_load_removes_leftover_temp_file()
{
    MemoryFs fs;
    fs.files["/quotes.txt"] = "2026-10-19|Aktuell\n";
    fs.files["/quotes.new"] = "2026-10-20|Halbfertig\n";
    QuoteList l = QuoteStore(fs).load();
    TEST_ASSERT_FALSE(fs.exists("/quotes.new"));
    TEST_ASSERT_EQUAL(1, l.size());
    TEST_ASSERT_EQUAL_STRING("Aktuell", l.at(0).text.c_str());
}

void test_load_migrates_legacy_text()
{
    MemoryFs fs;
    fs.files["/text.txt"] = "Alter Text\r\n";
    QuoteList l = QuoteStore(fs).load();
    TEST_ASSERT_EQUAL(1, l.size());
    TEST_ASSERT_EQUAL_STRING("", l.at(0).date.c_str());
    TEST_ASSERT_EQUAL_STRING("Alter Text", l.at(0).text.c_str());
    TEST_ASSERT_FALSE(fs.exists("/text.txt"));
    TEST_ASSERT_EQUAL_STRING("|Alter Text\n", fs.files["/quotes.txt"].c_str());
}

void test_load_ignores_empty_legacy_text()
{
    MemoryFs fs;
    fs.files["/text.txt"] = "\r\n";
    TEST_ASSERT_TRUE(QuoteStore(fs).load().empty());
    TEST_ASSERT_TRUE(fs.exists("/text.txt"));
}

void test_load_prefers_quotes_over_legacy()
{
    MemoryFs fs;
    fs.files["/quotes.txt"] = "2026-10-19|Neu\n";
    fs.files["/text.txt"] = "Alter Text\r\n";
    QuoteList l = QuoteStore(fs).load();
    TEST_ASSERT_EQUAL(1, l.size());
    TEST_ASSERT_EQUAL_STRING("Neu", l.at(0).text.c_str());
    TEST_ASSERT_TRUE(fs.exists("/text.txt"));
}

void test_save_writes_quotes_and_no_temp_left()
{
    MemoryFs fs;
    QuoteList l;
    l.addNewest("2026-10-19", "Hallo");
    TEST_ASSERT_TRUE(QuoteStore(fs).save(l));
    TEST_ASSERT_EQUAL_STRING(l.serialize().c_str(), fs.files["/quotes.txt"].c_str());
    TEST_ASSERT_FALSE(fs.exists("/quotes.new"));
}

void test_save_keeps_old_file_when_rename_fails()
{
    MemoryFs fs;
    fs.files["/quotes.txt"] = "2026-10-18|Alt\n";
    fs.failRename = true;
    QuoteList l;
    l.addNewest("2026-10-19", "Neu");
    TEST_ASSERT_FALSE(QuoteStore(fs).save(l));
    TEST_ASSERT_EQUAL_STRING("2026-10-18|Alt\n", fs.files["/quotes.txt"].c_str());
}

void test_save_refused_after_unreadable_quotes()
{
    MemoryFs fs;
    fs.files["/quotes.txt"] = "2026-10-18|Alt\n";
    fs.failRead = true;
    QuoteStore store(fs);
    TEST_ASSERT_TRUE(store.load().empty());
    QuoteList l;
    l.addNewest("2026-10-19", "Neu");
    TEST_ASSERT_FALSE(store.save(l));
    TEST_ASSERT_EQUAL_STRING("2026-10-18|Alt\n", fs.files["/quotes.txt"].c_str());
    TEST_ASSERT_FALSE(fs.exists("/quotes.new"));
}

void test_successful_load_clears_refusal()
{
    MemoryFs fs;
    fs.files["/quotes.txt"] = "2026-10-18|Alt\n";
    QuoteStore store(fs);
    fs.failRead = true;
    store.load();
    fs.failRead = false;
    QuoteList l = store.load();
    TEST_ASSERT_EQUAL(1, l.size());
    l.addNewest("2026-10-19", "Neu");
    TEST_ASSERT_TRUE(store.save(l));
    TEST_ASSERT_EQUAL_STRING("2026-10-19|Neu\n2026-10-18|Alt\n", fs.files["/quotes.txt"].c_str());
}

int main(int, char**)
{
    UNITY_BEGIN();
    RUN_TEST(test_load_without_files_is_empty);
    RUN_TEST(test_load_removes_leftover_temp_file);
    RUN_TEST(test_load_migrates_legacy_text);
    RUN_TEST(test_load_ignores_empty_legacy_text);
    RUN_TEST(test_load_prefers_quotes_over_legacy);
    RUN_TEST(test_save_writes_quotes_and_no_temp_left);
    RUN_TEST(test_save_keeps_old_file_when_rename_fails);
    RUN_TEST(test_save_refused_after_unreadable_quotes);
    RUN_TEST(test_successful_load_clears_refusal);
    return UNITY_END();
}
