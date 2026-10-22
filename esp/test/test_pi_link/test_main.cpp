#include <unity.h>
#include <string>
#include "PiLink.h"
#include "../support/MemorySerial.h"

using K = LinkEvent::Kind;

void setUp() {}
void tearDown() {}

static size_t countOf(const std::string& s, const std::string& what)
{
    size_t n = 0, p = 0;
    while ((p = s.find(what, p)) != std::string::npos) { ++n; p += what.size(); }
    return n;
}

void test_send_writes_newline_and_one_frame()
{
    MemorySerial s; PiLink l(s);
    TEST_ASSERT_TRUE(l.send("PING", "", 0));
    TEST_ASSERT_EQUAL_STRING("\n$00:PING*2A\n", s.takeTx().c_str());
}

void test_repeats_every_250ms_until_answer()
{
    MemorySerial s; PiLink l(s);
    l.send("PING", "", 0); s.takeTx();
    TEST_ASSERT_TRUE(l.poll(249).kind == K::None);
    TEST_ASSERT_EQUAL_STRING("", s.takeTx().c_str());
    l.poll(250);
    TEST_ASSERT_EQUAL_STRING("\n$00:PING*2A\n", s.takeTx().c_str());
    s.rx = "$00:PONG*2C\n";
    LinkEvent e = l.poll(300);
    TEST_ASSERT_TRUE(e.kind == K::Response);
    TEST_ASSERT_EQUAL_UINT8(0, e.message.seq);
    TEST_ASSERT_EQUAL_STRING("PONG", e.message.command.c_str());
    TEST_ASSERT_FALSE(l.busy());
    l.poll(600);
    TEST_ASSERT_EQUAL_STRING("", s.takeTx().c_str());
}

void test_expires_after_deadline_with_12_frames()
{
    MemorySerial s; PiLink l(s);
    l.send("PING", "", 0);
    for (unsigned long t = 10; t <= 2990; t += 10)
        TEST_ASSERT_TRUE(l.poll(t).kind == K::None);
    LinkEvent e = l.poll(3000);
    TEST_ASSERT_TRUE(e.kind == K::Expired);
    TEST_ASSERT_EQUAL_STRING("PING", e.message.command.c_str());
    TEST_ASSERT_EQUAL_UINT32(12, countOf(s.tx, "$00:PING*2A"));
    TEST_ASSERT_FALSE(l.busy());
}

void test_get_quote_waits_120s()
{
    MemorySerial s; PiLink l(s);
    TEST_ASSERT_TRUE(l.send("GET", "QUOTE|", 0));
    TEST_ASSERT_EQUAL_STRING("\n$00:GET|QUOTE|*36\n", s.takeTx().c_str());
    TEST_ASSERT_TRUE(l.poll(119999).kind != K::Expired);
    TEST_ASSERT_TRUE(l.poll(120000).kind == K::Expired);
}

void test_numbers_count_per_request_not_per_repeat()
{
    MemorySerial s; PiLink l(s);
    l.send("PING", "", 0); s.takeTx();
    l.poll(250);
    TEST_ASSERT_EQUAL_STRING("\n$00:PING*2A\n", s.takeTx().c_str());
    s.rx = "$00:PONG*2C\n";
    TEST_ASSERT_TRUE(l.poll(300).kind == K::Response);
    l.send("PING", "", 400);
    TEST_ASSERT_EQUAL_STRING("\n$01:PING*2B\n", s.takeTx().c_str());
}

void test_number_wraps_from_ff_to_00()
{
    MemorySerial s; PiLink l(s);
    LinkState st; st.txSeq = 0xFF;
    l.restore(st);
    l.send("PING", "", 0);
    TEST_ASSERT_EQUAL_STRING("\n$FF:PING*2A\n", s.takeTx().c_str());
    s.rx = "$FF:PONG*2C\n";
    TEST_ASSERT_TRUE(l.poll(10).kind == K::Response);
    l.send("PING", "", 20);
    TEST_ASSERT_EQUAL_STRING("\n$00:PING*2A\n", s.takeTx().c_str());
}

void test_second_send_while_open_is_refused()
{
    MemorySerial s; PiLink l(s);
    l.send("PING", "", 0);
    TEST_ASSERT_FALSE(l.send("BUTTON", "1", 10));
    TEST_ASSERT_EQUAL_STRING("\n$00:PING*2A\n", s.takeTx().c_str());
}

void test_send_refuses_unencodable_data()
{
    MemorySerial s; PiLink l(s);
    TEST_ASSERT_FALSE(l.send("GET", "QUOTE|\xC4", 0));
    TEST_ASSERT_FALSE(l.busy());
    TEST_ASSERT_EQUAL_STRING("", s.takeTx().c_str());
    l.send("PING", "", 0);
    TEST_ASSERT_EQUAL_STRING("\n$00:PING*2A\n", s.takeTx().c_str());
}

void test_late_answer_for_previous_number_is_ignored()
{
    MemorySerial s; PiLink l(s);
    l.send("PING", "", 0);
    s.rx = "$00:PONG*2C\n";
    TEST_ASSERT_TRUE(l.poll(10).kind == K::Response);
    l.send("PING", "", 20);
    s.rx = "$00:PONG*2C\n";
    TEST_ASSERT_TRUE(l.poll(30).kind == K::None);
    TEST_ASSERT_TRUE(l.busy());
}

void test_answer_without_open_request_is_ignored()
{
    MemorySerial s; PiLink l(s);
    s.rx = "$00:PONG*2C\n";
    TEST_ASSERT_TRUE(l.poll(0).kind == K::None);
    TEST_ASSERT_EQUAL_UINT32(0, l.discarded());
}

void test_request_from_pi_is_delivered_and_answered()
{
    MemorySerial s; PiLink l(s);
    s.rx = "$05:READY*74\n";
    LinkEvent e = l.poll(0);
    TEST_ASSERT_TRUE(e.kind == K::Request);
    TEST_ASSERT_EQUAL_UINT8(5, e.message.seq);
    TEST_ASSERT_EQUAL_STRING("READY", e.message.command.c_str());
    TEST_ASSERT_TRUE(l.reply("OK"));
    TEST_ASSERT_EQUAL_STRING("\n$05:OK*3B\n", s.takeTx().c_str());
}

void test_duplicate_gets_previous_answer_again()
{
    MemorySerial s; PiLink l(s);
    s.rx = "$05:READY*74\n";
    l.poll(0); l.reply("OK"); s.takeTx();
    s.rx = "$05:READY*74\n";
    TEST_ASSERT_TRUE(l.poll(10).kind == K::None);
    TEST_ASSERT_EQUAL_STRING("\n$05:OK*3B\n", s.takeTx().c_str());
}

void test_duplicate_before_reply_is_ignored()
{
    MemorySerial s; PiLink l(s);
    s.rx = "$05:READY*74\n$05:READY*74\n";
    TEST_ASSERT_TRUE(l.poll(0).kind == K::Request);
    TEST_ASSERT_TRUE(l.poll(0).kind == K::None);
    TEST_ASSERT_EQUAL_STRING("", s.takeTx().c_str());
}

void test_new_number_is_new_request()
{
    MemorySerial s; PiLink l(s);
    s.rx = "$05:READY*74\n";
    l.poll(0); l.reply("OK");
    s.rx = "$06:READY*77\n";
    LinkEvent e = l.poll(10);
    TEST_ASSERT_TRUE(e.kind == K::Request);
    TEST_ASSERT_EQUAL_UINT8(6, e.message.seq);
}

void test_unknown_command_is_answered_with_error_unknown()
{
    MemorySerial s; PiLink l(s);
    s.rx = "$07:PING*2D\n";
    TEST_ASSERT_TRUE(l.poll(0).kind == K::None);
    TEST_ASSERT_EQUAL_STRING("\n$07:ERROR|UNKNOWN*51\n", s.takeTx().c_str());
    s.rx = "$07:PING*2D\n";
    TEST_ASSERT_TRUE(l.poll(10).kind == K::None);
    TEST_ASSERT_EQUAL_STRING("\n$07:ERROR|UNKNOWN*51\n", s.takeTx().c_str());
}

void test_bad_line_is_counted_and_not_answered()
{
    MemorySerial s; PiLink l(s);
    s.rx = "$00:PING*2B\n";
    TEST_ASSERT_TRUE(l.poll(0).kind == K::None);
    TEST_ASSERT_EQUAL_UINT32(1, l.discarded());
    TEST_ASSERT_TRUE(l.lastError() == LinkCodec::Error::BadChecksum);
    TEST_ASSERT_EQUAL_STRING("", s.takeTx().c_str());
}

void test_too_long_line_is_dropped_and_next_line_is_read()
{
    MemorySerial s; PiLink l(s);
    s.rx = std::string(300, 'A') + "\n$05:READY*74\n";
    TEST_ASSERT_TRUE(l.poll(0).kind == K::Request);
    TEST_ASSERT_EQUAL_UINT32(1, l.discarded());
    TEST_ASSERT_TRUE(l.lastError() == LinkCodec::Error::TooLong);
}

void test_partial_line_waits_for_newline()
{
    MemorySerial s; PiLink l(s);
    s.rx = "$05:REA";
    TEST_ASSERT_TRUE(l.poll(0).kind == K::None);
    s.rx += "DY*74\n";
    TEST_ASSERT_TRUE(l.poll(1).kind == K::Request);
}

void test_crlf_is_accepted()
{
    MemorySerial s; PiLink l(s);
    s.rx = "$05:READY*74\r\n";
    TEST_ASSERT_TRUE(l.poll(0).kind == K::Request);
}

void test_empty_lines_are_not_counted()
{
    MemorySerial s; PiLink l(s);
    s.rx = "\n\r\n\n";
    TEST_ASSERT_TRUE(l.poll(0).kind == K::None);
    TEST_ASSERT_EQUAL_UINT32(0, l.discarded());
}

void test_reply_without_request_is_refused()
{
    MemorySerial s; PiLink l(s);
    TEST_ASSERT_FALSE(l.reply("OK"));
    TEST_ASSERT_EQUAL_STRING("", s.takeTx().c_str());
}

void test_state_survives_restore()
{
    MemorySerial sa; PiLink a(sa);
    a.send("PING", "", 0); sa.takeTx();
    sa.rx = "$00:PONG*2C\n$05:READY*74\n";
    TEST_ASSERT_TRUE(a.poll(10).kind == K::Response);
    TEST_ASSERT_TRUE(a.poll(10).kind == K::Request);
    a.reply("OK");
    LinkState st = a.state();
    TEST_ASSERT_EQUAL_UINT8(1, st.txSeq);
    TEST_ASSERT_EQUAL_UINT8(5, st.rxSeq);
    TEST_ASSERT_TRUE(st.rxValid);

    MemorySerial sb; PiLink b(sb);
    b.restore(st);
    b.send("PING", "", 0);
    TEST_ASSERT_EQUAL_STRING("\n$01:PING*2B\n", sb.takeTx().c_str());
    sb.rx = "$05:READY*74\n";
    TEST_ASSERT_TRUE(b.poll(10).kind == K::None);
    TEST_ASSERT_EQUAL_STRING("", sb.takeTx().c_str());
}

int main(int, char**)
{
    UNITY_BEGIN();
    RUN_TEST(test_send_writes_newline_and_one_frame);
    RUN_TEST(test_repeats_every_250ms_until_answer);
    RUN_TEST(test_expires_after_deadline_with_12_frames);
    RUN_TEST(test_get_quote_waits_120s);
    RUN_TEST(test_numbers_count_per_request_not_per_repeat);
    RUN_TEST(test_number_wraps_from_ff_to_00);
    RUN_TEST(test_second_send_while_open_is_refused);
    RUN_TEST(test_send_refuses_unencodable_data);
    RUN_TEST(test_late_answer_for_previous_number_is_ignored);
    RUN_TEST(test_answer_without_open_request_is_ignored);
    RUN_TEST(test_request_from_pi_is_delivered_and_answered);
    RUN_TEST(test_duplicate_gets_previous_answer_again);
    RUN_TEST(test_duplicate_before_reply_is_ignored);
    RUN_TEST(test_new_number_is_new_request);
    RUN_TEST(test_unknown_command_is_answered_with_error_unknown);
    RUN_TEST(test_bad_line_is_counted_and_not_answered);
    RUN_TEST(test_too_long_line_is_dropped_and_next_line_is_read);
    RUN_TEST(test_partial_line_waits_for_newline);
    RUN_TEST(test_crlf_is_accepted);
    RUN_TEST(test_empty_lines_are_not_counted);
    RUN_TEST(test_reply_without_request_is_refused);
    RUN_TEST(test_state_survives_restore);
    return UNITY_END();
}
