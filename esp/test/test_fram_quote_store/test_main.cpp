#include <unity.h>
#include <string>
#include "FramQuoteStore.h"
#include "../support/MemoryFs.h"
#include "../support/MemoryBytes.h"

void setUp() {}
void tearDown() {}

static void putList(MemoryBytes& fram, const std::string& text)
{
    QuoteList l;
    l.addNewest("2026-10-01", text);
    TEST_ASSERT_TRUE(SlotStore(fram).write(l.serialize()));
}

void test_load_imports_mailbox_and_removes_file()
{
    MemoryBytes fram;
    MemoryFs fs;
    fs.files["/quotes.txt"] = "2026-10-21|Neu\n";
    FramQuoteStore store(fram, fs);
    QuoteList l = store.load();
    TEST_ASSERT_EQUAL(1, l.size());
    TEST_ASSERT_EQUAL_STRING("Neu", l.at(0).text.c_str());
    TEST_ASSERT_FALSE(fs.exists("/quotes.txt"));
    TEST_ASSERT_TRUE(store.lastLoad().imported);
    TEST_ASSERT_FALSE(store.lastLoad().importFailed);
    FramQuoteStore second(fram, fs);
    QuoteList l2 = second.load();
    TEST_ASSERT_EQUAL(1, l2.size());
    TEST_ASSERT_EQUAL_STRING("Neu", l2.at(0).text.c_str());
    TEST_ASSERT_FALSE(second.lastLoad().imported);
}

void test_import_removes_leftover_temp_file()
{
    MemoryBytes fram;
    MemoryFs fs;
    fs.files["/quotes.txt"] = "2026-10-21|Neu\n";
    fs.files["/quotes.new"] = "2026-10-22|Halbfertig\n";
    FramQuoteStore(fram, fs).load();
    TEST_ASSERT_FALSE(fs.exists("/quotes.new"));
    TEST_ASSERT_FALSE(fs.exists("/quotes.txt"));
}

void test_load_imports_legacy_text()
{
    MemoryBytes fram;
    MemoryFs fs;
    fs.files["/text.txt"] = "Alter Text\r\n";
    FramQuoteStore store(fram, fs);
    QuoteList l = store.load();
    TEST_ASSERT_EQUAL(1, l.size());
    TEST_ASSERT_EQUAL_STRING("", l.at(0).date.c_str());
    TEST_ASSERT_EQUAL_STRING("Alter Text", l.at(0).text.c_str());
    TEST_ASSERT_FALSE(fs.exists("/text.txt"));
    TEST_ASSERT_TRUE(store.lastLoad().imported);
    TEST_ASSERT_EQUAL_STRING("Alter Text", FramQuoteStore(fram, fs).load().at(0).text.c_str());
}

void test_load_ignores_empty_legacy_text()
{
    MemoryBytes fram;
    MemoryFs fs;
    putList(fram, "A");
    fs.files["/text.txt"] = "\r\n";
    FramQuoteStore store(fram, fs);
    QuoteList l = store.load();
    TEST_ASSERT_EQUAL(1, l.size());
    TEST_ASSERT_EQUAL_STRING("A", l.at(0).text.c_str());
    TEST_ASSERT_TRUE(fs.exists("/text.txt"));
    TEST_ASSERT_FALSE(store.lastLoad().imported);
}

void test_mailbox_replaces_existing_fram_list()
{
    MemoryBytes fram;
    MemoryFs fs;
    putList(fram, "A");
    fs.files["/quotes.txt"] = "2026-10-21|B\n";
    QuoteList l = FramQuoteStore(fram, fs).load();
    TEST_ASSERT_EQUAL(1, l.size());
    TEST_ASSERT_EQUAL_STRING("B", l.at(0).text.c_str());
}

void test_load_without_mailbox_keeps_fram_list()
{
    MemoryBytes fram;
    MemoryFs fs;
    putList(fram, "A");
    FramQuoteStore store(fram, fs);
    QuoteList l = store.load();
    TEST_ASSERT_EQUAL(1, l.size());
    TEST_ASSERT_EQUAL_STRING("A", l.at(0).text.c_str());
    TEST_ASSERT_TRUE(fs.files.empty());
    TEST_ASSERT_FALSE(store.lastLoad().imported);
    TEST_ASSERT_TRUE(store.lastLoad().bytes > 0);
}

void test_mailbox_import_also_drops_legacy_text()
{
    MemoryBytes fram;
    MemoryFs fs;
    fs.files["/quotes.txt"] = "2026-10-21|Neu\n";
    fs.files["/text.txt"] = "Alter Text\n";
    QuoteList l = FramQuoteStore(fram, fs).load();
    TEST_ASSERT_EQUAL(1, l.size());
    TEST_ASSERT_EQUAL_STRING("Neu", l.at(0).text.c_str());
    TEST_ASSERT_FALSE(fs.exists("/quotes.txt"));
    TEST_ASSERT_FALSE(fs.exists("/text.txt"));
    QuoteList l2 = FramQuoteStore(fram, fs).load();
    TEST_ASSERT_EQUAL(1, l2.size());
    TEST_ASSERT_EQUAL_STRING("Neu", l2.at(0).text.c_str());
}

void test_load_imports_empty_mailbox_file()
{
    MemoryBytes fram;
    MemoryFs fs;
    putList(fram, "A");
    fs.files["/quotes.txt"] = "";
    FramQuoteStore store(fram, fs);
    TEST_ASSERT_TRUE(store.load().empty());
    TEST_ASSERT_FALSE(fs.exists("/quotes.txt"));
    TEST_ASSERT_TRUE(store.lastLoad().imported);
    TEST_ASSERT_TRUE(FramQuoteStore(fram, fs).load().empty());
}

void test_bus_error_gives_empty_list_and_refuses_save()
{
    MemoryBytes fram;
    MemoryFs fs;
    putList(fram, "A");
    fram.failRead = true;
    FramQuoteStore store(fram, fs);
    TEST_ASSERT_TRUE(store.load().empty());
    TEST_ASSERT_TRUE(store.lastLoad().busError);
    fram.failRead = false;
    QuoteList l;
    l.addNewest("2026-10-02", "X");
    TEST_ASSERT_FALSE(store.save(l));
    TEST_ASSERT_EQUAL_STRING("A", FramQuoteStore(fram, fs).load().at(0).text.c_str());
}

void test_failed_import_keeps_file_shows_list_and_refuses_save()
{
    MemoryBytes fram;
    MemoryFs fs;
    fs.files["/quotes.txt"] = "2026-10-21|Neu\n";
    fram.failWrite = true;
    FramQuoteStore store(fram, fs);
    QuoteList l = store.load();
    TEST_ASSERT_EQUAL(1, l.size());
    TEST_ASSERT_EQUAL_STRING("Neu", l.at(0).text.c_str());
    TEST_ASSERT_TRUE(fs.exists("/quotes.txt"));
    TEST_ASSERT_TRUE(store.lastLoad().importFailed);
    TEST_ASSERT_FALSE(store.lastLoad().imported);
    fram.failWrite = false;
    TEST_ASSERT_FALSE(store.save(l));
}

void test_unreadable_mailbox_is_kept_and_fram_is_read()
{
    MemoryBytes fram;
    MemoryFs fs;
    putList(fram, "A");
    fs.files["/quotes.txt"] = "2026-10-21|Neu\n";
    fs.failRead = true;
    FramQuoteStore store(fram, fs);
    QuoteList l = store.load();
    TEST_ASSERT_EQUAL(1, l.size());
    TEST_ASSERT_EQUAL_STRING("A", l.at(0).text.c_str());
    TEST_ASSERT_TRUE(fs.exists("/quotes.txt"));
    TEST_ASSERT_FALSE(store.lastLoad().imported);
}

void test_save_then_load_round_trip()
{
    MemoryBytes fram;
    MemoryFs fs;
    FramQuoteStore store(fram, fs);
    store.load();
    QuoteList l;
    l.addNewest("2026-10-01", "Eins");
    l.addNewest("2026-10-02", "Zwei");
    TEST_ASSERT_TRUE(store.save(l));
    QuoteList r = FramQuoteStore(fram, fs).load();
    TEST_ASSERT_EQUAL_STRING(l.serialize().c_str(), r.serialize().c_str());
    TEST_ASSERT_EQUAL(2, r.size());
}

int main(int, char**)
{
    UNITY_BEGIN();
    RUN_TEST(test_load_imports_mailbox_and_removes_file);
    RUN_TEST(test_import_removes_leftover_temp_file);
    RUN_TEST(test_load_imports_legacy_text);
    RUN_TEST(test_load_ignores_empty_legacy_text);
    RUN_TEST(test_mailbox_replaces_existing_fram_list);
    RUN_TEST(test_load_without_mailbox_keeps_fram_list);
    RUN_TEST(test_mailbox_import_also_drops_legacy_text);
    RUN_TEST(test_load_imports_empty_mailbox_file);
    RUN_TEST(test_bus_error_gives_empty_list_and_refuses_save);
    RUN_TEST(test_failed_import_keeps_file_shows_list_and_refuses_save);
    RUN_TEST(test_unreadable_mailbox_is_kept_and_fram_is_read);
    RUN_TEST(test_save_then_load_round_trip);
    return UNITY_END();
}
