#include <unity.h>
#include <string>
#include "Crc32.h"
#include "SlotStore.h"
#include "../support/MemoryBytes.h"

void setUp() {}
void tearDown() {}

static std::string readContent(MemoryBytes& m, SlotStore::ReadResult expected)
{
    std::string content;
    TEST_ASSERT_EQUAL(static_cast<int>(expected), static_cast<int>(SlotStore(m).read(content)));
    return content;
}

void test_crc32_check_value()
{
    const char* s = "123456789";
    TEST_ASSERT_EQUAL_HEX32(0xCBF43926, crc32Ieee(reinterpret_cast<const uint8_t*>(s), 9));
}

void test_crc32_can_continue()
{
    const uint8_t a[] = {'1', '2', '3', '4', '5'};
    const uint8_t b[] = {'6', '7', '8', '9'};
    TEST_ASSERT_EQUAL_HEX32(0xCBF43926, crc32Ieee(b, 4, crc32Ieee(a, 5)));
}

void test_read_blank_is_empty()
{
    MemoryBytes m;
    TEST_ASSERT_EQUAL_STRING("", readContent(m, SlotStore::ReadResult::Empty).c_str());
}

void test_write_then_read()
{
    MemoryBytes m;
    TEST_ASSERT_TRUE(SlotStore(m).write("2026-10-19|Eins\n"));
    TEST_ASSERT_EQUAL_STRING("2026-10-19|Eins\n", readContent(m, SlotStore::ReadResult::Ok).c_str());
}

void test_first_write_goes_to_slot_a_with_number_1()
{
    MemoryBytes m;
    TEST_ASSERT_TRUE(SlotStore(m).write("x"));
    const uint8_t head[8] = {0x52, 0x57, 0x51, 0x31, 0x01, 0x00, 0x00, 0x00};
    TEST_ASSERT_EQUAL_UINT8_ARRAY(head, &m.data[0], 8);
    for (std::size_t i = 0; i < SlotLayout::SLOT_SIZE; ++i)
    {
        TEST_ASSERT_EQUAL_UINT8(0, m.data[SlotLayout::SLOT_B + i]);
    }
}

void test_second_write_goes_to_slot_b()
{
    MemoryBytes m;
    SlotStore s(m);
    TEST_ASSERT_TRUE(s.write("eins"));
    TEST_ASSERT_TRUE(s.write("zwei"));
    TEST_ASSERT_EQUAL_UINT8(0x52, m.data[SlotLayout::SLOT_B]);
    TEST_ASSERT_EQUAL_UINT8(2, m.data[SlotLayout::SLOT_B + 4]);
    TEST_ASSERT_EQUAL_STRING("zwei", readContent(m, SlotStore::ReadResult::Ok).c_str());
}

void test_third_write_goes_back_to_slot_a()
{
    MemoryBytes m;
    SlotStore s(m);
    s.write("eins");
    s.write("zwei");
    TEST_ASSERT_TRUE(s.write("drei"));
    TEST_ASSERT_EQUAL_UINT8(3, m.data[4]);
    TEST_ASSERT_EQUAL_STRING("drei", readContent(m, SlotStore::ReadResult::Ok).c_str());
}

void test_interrupted_write_keeps_previous_list()
{
    MemoryBytes m;
    SlotStore s(m);
    s.write("alt1");
    s.write("alt2");
    m.writeBudget = 5;
    TEST_ASSERT_FALSE(s.write("neu"));
    m.writeBudget = -1;
    TEST_ASSERT_EQUAL_STRING("alt2", readContent(m, SlotStore::ReadResult::Ok).c_str());
}

void test_header_with_oversized_length_is_ignored()
{
    MemoryBytes m;
    const uint8_t head[16] = {0x52, 0x57, 0x51, 0x31, 0x01, 0x00, 0x00, 0x00,
                              0xF1, 0x0F, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00};   // Laenge 4081
    // gueltige Pruefsumme ueber die 4081 Nullbytes dahinter, damit nur die Laengenpruefung ablehnen kann
    const std::vector<uint8_t> zeros(4081, 0);
    const uint32_t crc = crc32Ieee(zeros.data(), zeros.size(), crc32Ieee(head + 4, 8));
    for (int i = 0; i < 4; ++i)
    {
        m.data[SlotLayout::SLOT_A + 12 + i] = static_cast<uint8_t>(crc >> (8 * i));
    }
    for (std::size_t i = 0; i < 12; ++i)
    {
        m.data[SlotLayout::SLOT_A + i] = head[i];
    }
    TEST_ASSERT_EQUAL_STRING("", readContent(m, SlotStore::ReadResult::Damaged).c_str());
}

void test_half_written_header_keeps_previous_list()
{
    MemoryBytes m;
    SlotStore s(m);
    s.write("alt1");
    s.write("alt2");
    m.writeBudget = 3 + 8;   // "neu" ganz, vom Kopf nur die ersten 8 von 16 Bytes
    TEST_ASSERT_FALSE(s.write("neu"));
    m.writeBudget = -1;
    TEST_ASSERT_EQUAL_UINT8(3, m.data[SlotLayout::SLOT_A + 4]);   // Nummer im Kopf ist schon neu
    TEST_ASSERT_EQUAL_STRING("alt2", readContent(m, SlotStore::ReadResult::Ok).c_str());
}

void test_corrupt_newest_slot_falls_back()
{
    MemoryBytes m;
    SlotStore s(m);
    s.write("eins");
    s.write("zwei");
    m.data[SlotLayout::SLOT_B + SlotLayout::HEADER_SIZE] ^= 0x01;
    TEST_ASSERT_EQUAL_STRING("eins", readContent(m, SlotStore::ReadResult::Ok).c_str());
}

void test_too_long_content_is_refused()
{
    MemoryBytes m;
    const std::vector<uint8_t> before = m.data;
    TEST_ASSERT_FALSE(SlotStore(m).write(std::string(4081, 'x')));
    TEST_ASSERT_TRUE(before == m.data);
    TEST_ASSERT_TRUE(SlotStore(m).write(std::string(4080, 'x')));
    TEST_ASSERT_EQUAL(4080, readContent(m, SlotStore::ReadResult::Ok).size());
}

void test_read_error_is_bus_error()
{
    MemoryBytes m;
    m.failRead = true;
    readContent(m, SlotStore::ReadResult::BusError);
}

void test_write_without_read_continues_numbering()
{
    MemoryBytes m;
    SlotStore s1(m);
    s1.write("eins");
    s1.write("zwei");
    SlotStore s2(m);
    TEST_ASSERT_TRUE(s2.write("drei"));
    TEST_ASSERT_EQUAL_UINT8(3, m.data[4]);
    TEST_ASSERT_EQUAL_STRING("drei", readContent(m, SlotStore::ReadResult::Ok).c_str());
}

static void corruptList(MemoryBytes& m, uint16_t slot)
{
    m.data[slot + SlotLayout::HEADER_SIZE] ^= 0x01;
}

void test_single_bad_read_is_retried()
{
    MemoryBytes m;
    SlotStore s(m);
    s.write("alt-alt-alt-alt-alt-alt");
    s.write("neu-neu-neu-neu-neu-neu");
    m.corruptReads = 1;
    TEST_ASSERT_EQUAL_STRING("neu-neu-neu-neu-neu-neu", readContent(m, SlotStore::ReadResult::Ok).c_str());
}

void test_number_continues_above_damaged_slot()
{
    MemoryBytes m;
    SlotStore s(m);
    s.write("a");
    s.write("b");
    corruptList(m, SlotLayout::SLOT_B);
    std::string content;
    TEST_ASSERT_EQUAL(static_cast<int>(SlotStore::ReadResult::Ok), static_cast<int>(s.read(content)));
    TEST_ASSERT_EQUAL_STRING("a", content.c_str());
    TEST_ASSERT_TRUE(s.write("c"));
    TEST_ASSERT_EQUAL_UINT8(3, m.data[SlotLayout::SLOT_B + 4]);
    TEST_ASSERT_EQUAL_STRING("c", readContent(m, SlotStore::ReadResult::Ok).c_str());
}

void test_both_slots_damaged_is_reported()
{
    MemoryBytes m;
    SlotStore s(m);
    s.write("a");
    s.write("b");
    corruptList(m, SlotLayout::SLOT_A);
    corruptList(m, SlotLayout::SLOT_B);
    TEST_ASSERT_EQUAL_STRING("", readContent(m, SlotStore::ReadResult::Damaged).c_str());
}

void test_number_above_both_damaged_slots()
{
    MemoryBytes m;
    SlotStore s(m);
    s.write("a");
    s.write("b");
    corruptList(m, SlotLayout::SLOT_A);
    corruptList(m, SlotLayout::SLOT_B);
    SlotStore fresh(m);
    TEST_ASSERT_TRUE(fresh.write("c"));
    TEST_ASSERT_EQUAL_UINT8(3, m.data[SlotLayout::SLOT_A + 4]);   // A hat die niedrigere Nummer 1
    TEST_ASSERT_EQUAL_STRING("c", readContent(m, SlotStore::ReadResult::Ok).c_str());
}

void test_write_after_failed_write_numbers_correctly()
{
    MemoryBytes m;
    SlotStore s(m);
    m.failWrite = true;
    TEST_ASSERT_FALSE(s.write("a"));
    m.failWrite = false;
    TEST_ASSERT_TRUE(s.write("b"));
    TEST_ASSERT_EQUAL_UINT8(1, m.data[SlotLayout::SLOT_A + 4]);
    TEST_ASSERT_EQUAL_STRING("b", readContent(m, SlotStore::ReadResult::Ok).c_str());
}

void test_bus_error_in_prewrite_read_fails_write()
{
    MemoryBytes m;
    const std::vector<uint8_t> before = m.data;
    m.failRead = true;
    TEST_ASSERT_FALSE(SlotStore(m).write("a"));
    TEST_ASSERT_TRUE(before == m.data);
}

// Kopf-Stoerungen: corruptHeaderReads trifft zuerst Kopf A, dann Kopf B (je erstes Lesen)
void test_older_header_number_misread_high_keeps_newest()
{
    MemoryBytes m;
    SlotStore s(m);
    s.write("alt-alt-alt");
    s.write("neu-neu-neu");
    m.corruptHeaderReads = 1;   // Nummer von A: 1 -> 5, hoeher als B
    SlotStore r(m);
    std::string c;
    TEST_ASSERT_EQUAL(static_cast<int>(SlotStore::ReadResult::Ok), static_cast<int>(r.read(c)));
    TEST_ASSERT_EQUAL_STRING("neu-neu-neu", c.c_str());
    TEST_ASSERT_TRUE(r.write("neuer"));
    TEST_ASSERT_EQUAL_STRING("neuer", readContent(m, SlotStore::ReadResult::Ok).c_str());
}

void test_newest_number_misread_low_keeps_numbering()
{
    MemoryBytes m;
    SlotStore s(m);
    for (int i = 0; i < 6; ++i)
    {
        s.write(i % 2 ? "bbbbbbbb" : "aaaaaaaa");
    }
    for (std::size_t i = 0; i < SlotLayout::HEADER_SIZE; ++i)
    {
        m.data[SlotLayout::SLOT_A + i] = 0;   // A hat den Kopf verloren, B ist 6
    }
    m.corruptHeaderReads = 2;   // A leer (harmlos), Nummer von B: 6 -> 2
    SlotStore r(m);
    std::string c;
    TEST_ASSERT_EQUAL(static_cast<int>(SlotStore::ReadResult::Ok), static_cast<int>(r.read(c)));
    TEST_ASSERT_TRUE(r.write("neu"));
    TEST_ASSERT_EQUAL_UINT8(7, m.data[SlotLayout::SLOT_A + 4]);
    TEST_ASSERT_EQUAL_STRING("neu", readContent(m, SlotStore::ReadResult::Ok).c_str());
}

void test_misread_magic_on_newest_slot_is_retried()
{
    MemoryBytes m;
    SlotStore s(m);
    s.write("eins-eins");
    s.write("zwei-zwei");
    s.write("drei-drei");   // A ist neu
    m.corruptHeaderReads = 1;
    m.headerFlipByte = 0;
    m.headerFlipMask = 0x01;
    TEST_ASSERT_EQUAL_STRING("drei-drei", readContent(m, SlotStore::ReadResult::Ok).c_str());
}

void test_misread_length_on_newest_slot_is_retried()
{
    MemoryBytes m;
    SlotStore s(m);
    s.write("eins-eins");
    s.write("zwei-zwei");
    s.write("drei-drei");
    m.corruptHeaderReads = 1;
    m.headerFlipByte = 9;
    m.headerFlipMask = 0x20;   // Laenge ueber 4080
    TEST_ASSERT_EQUAL_STRING("drei-drei", readContent(m, SlotStore::ReadResult::Ok).c_str());
}

void test_both_headers_misread_once_is_not_empty()
{
    MemoryBytes m;
    SlotStore s(m);
    s.write("alt-alt");
    s.write("neu-neu");
    m.corruptHeaderReads = 2;
    m.headerFlipByte = 0;
    m.headerFlipMask = 0x01;
    SlotStore r(m);
    std::string c;
    TEST_ASSERT_EQUAL(static_cast<int>(SlotStore::ReadResult::Ok), static_cast<int>(r.read(c)));
    TEST_ASSERT_EQUAL_STRING("neu-neu", c.c_str());
    TEST_ASSERT_TRUE(r.write("drei"));
    TEST_ASSERT_EQUAL_UINT8(3, m.data[SlotLayout::SLOT_A + 4]);
}

int main(int, char**)
{
    UNITY_BEGIN();
    RUN_TEST(test_crc32_check_value);
    RUN_TEST(test_crc32_can_continue);
    RUN_TEST(test_read_blank_is_empty);
    RUN_TEST(test_write_then_read);
    RUN_TEST(test_first_write_goes_to_slot_a_with_number_1);
    RUN_TEST(test_second_write_goes_to_slot_b);
    RUN_TEST(test_third_write_goes_back_to_slot_a);
    RUN_TEST(test_interrupted_write_keeps_previous_list);
    RUN_TEST(test_header_with_oversized_length_is_ignored);
    RUN_TEST(test_half_written_header_keeps_previous_list);
    RUN_TEST(test_corrupt_newest_slot_falls_back);
    RUN_TEST(test_too_long_content_is_refused);
    RUN_TEST(test_read_error_is_bus_error);
    RUN_TEST(test_write_without_read_continues_numbering);
    RUN_TEST(test_single_bad_read_is_retried);
    RUN_TEST(test_number_continues_above_damaged_slot);
    RUN_TEST(test_both_slots_damaged_is_reported);
    RUN_TEST(test_number_above_both_damaged_slots);
    RUN_TEST(test_write_after_failed_write_numbers_correctly);
    RUN_TEST(test_bus_error_in_prewrite_read_fails_write);
    RUN_TEST(test_older_header_number_misread_high_keeps_newest);
    RUN_TEST(test_newest_number_misread_low_keeps_numbering);
    RUN_TEST(test_misread_magic_on_newest_slot_is_retried);
    RUN_TEST(test_misread_length_on_newest_slot_is_retried);
    RUN_TEST(test_both_headers_misread_once_is_not_empty);
    return UNITY_END();
}
