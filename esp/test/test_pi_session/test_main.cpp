#include <unity.h>
#include <cstring>
#include <string>
#include <vector>
#include "PiSession.h"

using K = LinkEvent::Kind;
using A = SessionAction::Kind;

#define TEST_ASSERT_STATE(s) TEST_ASSERT_EQUAL(static_cast<int>(SessionState::s), static_cast<int>(d.state))

static SessionData d;
static std::vector<SessionAction> out;
static LinkEvent ev(LinkEvent::Kind k, const char* cmd, const char* data = "") {
    LinkEvent e; e.kind = k; e.message.command = cmd; e.message.data = data; return e; }
static bool has(SessionAction::Kind k, const std::string& c = "", const std::string& v = "") {
    for (const auto& a : out) if (a.kind == k && (c.empty() || a.command == c) && (v.empty() || a.data == v)) return true;
    return false; }
void setUp() { PiSession::reset(d); out.clear(); }
void tearDown() {}

static int count(SessionAction::Kind k, const std::string& c = "")
{
    int n = 0;
    for (const auto& a : out) if (a.kind == k && (c.empty() || a.command == c)) ++n;
    return n;
}

// BETRIEB, SESSION beantwortet, keine Anfrage offen
static void toRunning(PiSession& s, bool hand = true)
{
    if (hand) s.startHand(out); else s.startNight(out);
    s.onLink(ev(K::Request, "READY"), out);
    s.onTick(0, false, out);
    s.onLink(ev(K::Response, "OK"), out);
    out.clear();
}

// HERUNTERFAHREN, SHUTDOWN gesendet
static void toShuttingDown(PiSession& s)
{
    toRunning(s);
    s.onButton(2, out);
    s.onTick(0, false, out);
    out.clear();
}

static void missPing(PiSession& s)
{
    s.onTick(10000, false, out);
    s.onLink(ev(K::Expired, "PING"), out);
}

void test_ready_replies_ok_then_tick_sends_session_hand() {
    PiSession s(d); s.startHand(out);
    TEST_ASSERT_TRUE(has(SessionAction::Kind::PowerOn));
    TEST_ASSERT_TRUE(has(SessionAction::Kind::Show, "PI STARTET"));
    out.clear(); s.onLink(ev(LinkEvent::Kind::Request, "READY"), out);
    TEST_ASSERT_TRUE(has(SessionAction::Kind::Reply, "OK"));
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(SessionAction::Kind::Send, "SESSION", "HAND"));
    TEST_ASSERT_EQUAL(static_cast<int>(SessionState::Running), static_cast<int>(d.state));
}

void test_no_ready_within_t_boot_is_hard_off_with_message_for_10_s() {
    PiSession s(d); s.startHand(out); out.clear();
    s.onTick(119999, false, out); TEST_ASSERT_FALSE(has(SessionAction::Kind::PowerOff));
    s.onTick(1, false, out);
    TEST_ASSERT_TRUE(has(SessionAction::Kind::PowerOff));
    TEST_ASSERT_TRUE(has(SessionAction::Kind::Show, "PI ANTWORTET NICHT"));
    TEST_ASSERT_TRUE(s.active());
    out.clear(); s.onTick(10000, false, out);
    TEST_ASSERT_TRUE(has(SessionAction::Kind::DisplayOff));
    TEST_ASSERT_FALSE(s.active());
}

void test_night_start_shows_nothing_and_sends_session_nacht()
{
    PiSession s(d); s.startNight(out);
    TEST_ASSERT_TRUE(has(A::PowerOn));
    TEST_ASSERT_FALSE(has(A::Show));
    s.onLink(ev(K::Request, "READY"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "OK"));
    s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SESSION", "NACHT"));
    TEST_ASSERT_FALSE(has(A::Show));
    TEST_ASSERT_FALSE(has(A::DisplayOff));
}

void test_no_ping_while_starting()
{
    PiSession s(d); s.startHand(out); out.clear();
    s.onTick(60000, false, out);
    TEST_ASSERT_FALSE(has(A::Send, "PING"));
    TEST_ASSERT_FALSE(has(A::Send));
    TEST_ASSERT_STATE(Starting);
}

void test_bt2_while_starting_shuts_down_after_ready_without_session()
{
    PiSession s(d); s.startHand(out);
    s.onButton(2, out);
    TEST_ASSERT_STATE(Starting);
    out.clear(); s.onLink(ev(K::Request, "READY"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "OK"));
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
    TEST_ASSERT_FALSE(has(A::Send, "SESSION"));
    TEST_ASSERT_STATE(ShuttingDown);

    PiSession::reset(d); out.clear();              // R9 gilt auch in der Nacht
    s.startNight(out);
    s.onButton(2, out);
    s.onLink(ev(K::Request, "READY"), out);
    s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
    TEST_ASSERT_FALSE(has(A::Send, "SESSION"));
}

void test_send_order_session_button_ping()
{
    PiSession s(d); toRunning(s);
    s.onTick(10000, true, out);                    // PING faellig, Leitung belegt
    s.onButton(3, out);
    s.onLink(ev(K::Request, "READY"), out);
    const char* const order[][2] = {{"SESSION", "HAND"}, {"BUTTON", "3"}, {"PING", ""}};
    for (const auto& o : order)
    {
        out.clear(); s.onTick(0, false, out);
        TEST_ASSERT_EQUAL(1, count(A::Send));
        TEST_ASSERT_TRUE(has(A::Send, o[0], o[1]));
        s.onLink(ev(K::Response, "OK"), out);
    }
}

void test_unknown_mode_is_error_unknown()
{
    PiSession s(d); toRunning(s);
    SessionData before = d;
    s.onLink(ev(K::Request, "MODE", "FAST"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "ERROR", "UNKNOWN"));
    TEST_ASSERT_EQUAL_MEMORY(&before, &d, sizeof d);
}

void test_ping_every_10_s()
{
    PiSession s(d); toRunning(s);
    s.onTick(9999, false, out);
    TEST_ASSERT_FALSE(has(A::Send, "PING"));
    s.onTick(1, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "PING"));
    s.onLink(ev(K::Response, "PONG"), out);
    out.clear(); s.onTick(9999, false, out);
    TEST_ASSERT_FALSE(has(A::Send, "PING"));
    s.onTick(1, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "PING"));
}

void test_three_missed_pings_hard_off_with_message()
{
    PiSession s(d); toRunning(s);
    missPing(s); missPing(s);
    TEST_ASSERT_FALSE(has(A::PowerOff));
    missPing(s);
    TEST_ASSERT_TRUE(has(A::PowerOff));
    TEST_ASSERT_TRUE(has(A::Show, "PI ANTWORTET NICHT"));
    TEST_ASSERT_STATE(Off);
    TEST_ASSERT_TRUE(s.active());
}

void test_pong_resets_missed_pings()
{
    PiSession s(d); toRunning(s);
    missPing(s); missPing(s);
    s.onTick(10000, false, out);
    s.onLink(ev(K::Response, "PONG"), out);
    missPing(s); missPing(s);
    TEST_ASSERT_FALSE(has(A::PowerOff));
    missPing(s);
    TEST_ASSERT_TRUE(has(A::PowerOff));
}

void test_ping_waits_while_link_busy()
{
    PiSession s(d); toRunning(s);
    s.onTick(20000, true, out);
    TEST_ASSERT_FALSE(has(A::Send));
    s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "PING"));
}

void test_ready_in_running_resends_session()
{
    PiSession s(d); toRunning(s);
    s.onLink(ev(K::Request, "READY"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "OK"));
    TEST_ASSERT_STATE(Running);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SESSION", "HAND"));
    TEST_ASSERT_STATE(Running);
}

void test_ready_in_radar_debug_returns_to_running()
{
    PiSession s(d); toRunning(s);
    s.onLink(ev(K::Request, "MODE", "RADAR"), out);
    TEST_ASSERT_STATE(RadarDebug);
    out.clear(); s.onLink(ev(K::Request, "READY"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "OK"));
    TEST_ASSERT_STATE(Running);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SESSION", "HAND"));
}

void test_done_starts_shutdown()
{
    PiSession s(d); toRunning(s);
    s.onLink(ev(K::Request, "DONE"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "OK"));
    TEST_ASSERT_STATE(ShuttingDown);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
}

void test_bt2_in_running_starts_shutdown()
{
    PiSession s(d); toRunning(s);
    s.onButton(2, out);
    TEST_ASSERT_STATE(ShuttingDown);
    s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
}

void test_shutdown_waits_for_free_link()
{
    PiSession s(d); toRunning(s);
    s.onTick(10000, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "PING"));
    s.onButton(2, out);
    out.clear(); s.onTick(0, true, out);
    TEST_ASSERT_FALSE(has(A::Send));
    s.onLink(ev(K::Response, "PONG"), out);
    s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
    s.onTick(0, true, out);
    s.onTick(0, false, out);
    TEST_ASSERT_EQUAL(1, count(A::Send));
}

void test_busy_retries_after_30_s()
{
    PiSession s(d); toShuttingDown(s);
    s.onLink(ev(K::Response, "BUSY"), out);
    s.onTick(29999, false, out);
    TEST_ASSERT_FALSE(has(A::Send));
    s.onTick(1, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
    s.onLink(ev(K::Response, "ERROR", "BUSY"), out);   // jede andere Antwort wie BUSY
    out.clear(); s.onTick(29999, false, out);
    TEST_ASSERT_FALSE(has(A::Send));
    s.onTick(1, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
    TEST_ASSERT_STATE(ShuttingDown);
}

void test_busy_for_10_min_is_hard_off_without_message()
{
    PiSession s(d); toShuttingDown(s);
    for (int i = 0; i < 19; ++i)
    {
        s.onLink(ev(K::Response, "BUSY"), out);
        s.onTick(30000, false, out);
    }
    TEST_ASSERT_EQUAL(19, count(A::Send, "SHUTDOWN"));
    s.onLink(ev(K::Response, "BUSY"), out);
    out.clear(); s.onTick(29999, false, out);
    TEST_ASSERT_FALSE(has(A::PowerOff));
    s.onTick(1, false, out);
    TEST_ASSERT_TRUE(has(A::PowerOff));
    TEST_ASSERT_TRUE(has(A::DisplayOff));
    TEST_ASSERT_FALSE(has(A::Show, "PI ANTWORTET NICHT"));
    TEST_ASSERT_FALSE(has(A::Send));
    TEST_ASSERT_STATE(Off);
    TEST_ASSERT_FALSE(s.active());
}

void test_shutdown_expired_is_hard_off_without_message()
{
    PiSession s(d); toShuttingDown(s);
    s.onLink(ev(K::Expired, "SHUTDOWN"), out);
    TEST_ASSERT_TRUE(has(A::PowerOff));
    TEST_ASSERT_TRUE(has(A::DisplayOff));
    TEST_ASSERT_FALSE(has(A::Show));
    TEST_ASSERT_STATE(Off);
    TEST_ASSERT_FALSE(s.active());
}

void test_ok_to_shutdown_shows_text_then_power_off_after_t_halt()
{
    PiSession s(d); toShuttingDown(s);
    s.onLink(ev(K::Response, "OK"), out);
    TEST_ASSERT_TRUE(has(A::Show, "PI FAEHRT HERUNTER"));
    TEST_ASSERT_STATE(Halting);
    out.clear(); s.onTick(29999, false, out);
    TEST_ASSERT_TRUE(out.empty());
    s.onTick(1, false, out);
    TEST_ASSERT_TRUE(has(A::PowerOff));
    TEST_ASSERT_TRUE(has(A::DisplayOff));
    TEST_ASSERT_TRUE(has(A::Log));                 // Dauer der Sitzung
    TEST_ASSERT_EQUAL_UINT32(30000, d.sessionMs);
    TEST_ASSERT_STATE(Off);
    TEST_ASSERT_FALSE(s.active());
}

void test_night_halting_has_no_display_actions()
{
    PiSession s(d); s.startNight(out);
    s.onLink(ev(K::Request, "READY"), out);
    s.onTick(0, false, out);
    s.onLink(ev(K::Response, "OK"), out);
    s.onLink(ev(K::Request, "DONE"), out);
    s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
    s.onLink(ev(K::Response, "OK"), out);
    TEST_ASSERT_STATE(Halting);
    s.onTick(30000, false, out);
    TEST_ASSERT_TRUE(has(A::PowerOff));
    TEST_ASSERT_STATE(Off);
    TEST_ASSERT_FALSE(has(A::Show));
    TEST_ASSERT_FALSE(has(A::DisplayOff));
}

void test_night_hard_off_leaves_display_alone()
{
    PiSession s(d); s.startNight(out);
    s.onTick(120000, false, out);                  // kein READY
    TEST_ASSERT_TRUE(has(A::PowerOff));
    TEST_ASSERT_FALSE(has(A::Show));
    TEST_ASSERT_FALSE(has(A::DisplayOff));
    TEST_ASSERT_FALSE(s.active());

    PiSession::reset(d); out.clear();
    toRunning(s, false);
    missPing(s); missPing(s); missPing(s);
    TEST_ASSERT_TRUE(has(A::PowerOff));
    TEST_ASSERT_FALSE(has(A::Show));
    TEST_ASSERT_FALSE(has(A::DisplayOff));
    TEST_ASSERT_FALSE(s.active());

    PiSession::reset(d); out.clear();
    toRunning(s, false);
    s.onLink(ev(K::Request, "DONE"), out);
    s.onTick(0, false, out);
    s.onLink(ev(K::Expired, "SHUTDOWN"), out);
    TEST_ASSERT_TRUE(has(A::PowerOff));
    TEST_ASSERT_FALSE(has(A::Show));
    TEST_ASSERT_FALSE(has(A::DisplayOff));
    TEST_ASSERT_STATE(Off);
}

void test_session_expired_starts_shutdown()
{
    PiSession s(d); s.startHand(out);
    s.onLink(ev(K::Request, "READY"), out);
    s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SESSION"));
    s.onLink(ev(K::Expired, "SESSION"), out);
    TEST_ASSERT_STATE(ShuttingDown);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
}

void test_session_answer_other_than_ok_starts_shutdown()
{
    PiSession s(d); s.startHand(out);
    s.onLink(ev(K::Request, "READY"), out);
    s.onTick(0, false, out);
    s.onLink(ev(K::Response, "ERROR", "UNKNOWN"), out);
    TEST_ASSERT_STATE(ShuttingDown);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
}

void test_session_failure_in_radar_debug_waits_like_bt2()
{
    PiSession s(d); toRunning(s);
    s.onLink(ev(K::Request, "READY"), out);
    s.onTick(0, false, out);                       // SESSION offen
    s.onLink(ev(K::Request, "MODE", "RADAR"), out);
    s.onLink(ev(K::Expired, "SESSION"), out);
    TEST_ASSERT_STATE(RadarDebug);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_FALSE(has(A::Send));
    s.onLink(ev(K::Request, "MODE", "NORMAL"), out);
    TEST_ASSERT_STATE(ShuttingDown);
    s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
}

void test_mode_radar_and_normal()
{
    PiSession s(d); toRunning(s);
    s.onLink(ev(K::Request, "MODE", "RADAR"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "OK"));
    TEST_ASSERT_STATE(RadarDebug);
    out.clear(); s.onTick(20000, false, out);
    TEST_ASSERT_FALSE(has(A::Send, "PING"));
    s.onLink(ev(K::Request, "MODE", "NORMAL"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "OK"));
    TEST_ASSERT_STATE(Running);
    out.clear(); s.onTick(9999, false, out);       // PING-Abstand beginnt neu
    TEST_ASSERT_FALSE(has(A::Send, "PING"));
    s.onTick(1, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "PING"));
}

void test_nothing_is_sent_in_radar_debug()
{
    PiSession s(d); toRunning(s);
    s.onTick(20000, true, out);                    // PING faellig, Leitung belegt
    s.onLink(ev(K::Request, "READY"), out);        // SESSION wartet
    s.onLink(ev(K::Request, "MODE", "RADAR"), out);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_FALSE(has(A::Send));
    s.onLink(ev(K::Request, "MODE", "NORMAL"), out);
    s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SESSION", "HAND"));
}

void test_mode_radar_outside_running_is_error_state()
{
    PiSession s(d); s.startHand(out);
    out.clear(); s.onLink(ev(K::Request, "MODE", "RADAR"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "ERROR", "STATE"));
    TEST_ASSERT_FALSE(has(A::Reply, "OK"));
    TEST_ASSERT_STATE(Starting);

    PiSession::reset(d); out.clear();
    toShuttingDown(s);
    s.onLink(ev(K::Request, "MODE", "RADAR"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "ERROR", "STATE"));
    TEST_ASSERT_FALSE(has(A::Reply, "OK"));
    TEST_ASSERT_STATE(ShuttingDown);

    s.onLink(ev(K::Response, "OK"), out);
    TEST_ASSERT_STATE(Halting);
    out.clear(); s.onLink(ev(K::Request, "MODE", "RADAR"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "ERROR", "STATE"));
    TEST_ASSERT_FALSE(has(A::Reply, "OK"));
    TEST_ASSERT_STATE(Halting);
}

void test_bt2_in_radar_debug_shuts_down_after_mode_normal()
{
    PiSession s(d); toRunning(s);
    s.onLink(ev(K::Request, "MODE", "RADAR"), out);
    s.onButton(2, out);
    TEST_ASSERT_STATE(RadarDebug);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_FALSE(has(A::Send));
    s.onLink(ev(K::Request, "MODE", "NORMAL"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "OK"));
    TEST_ASSERT_STATE(ShuttingDown);
    s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
}

void test_ready_in_radar_debug_with_bt2_shuts_down()
{
    PiSession s(d); toRunning(s);
    s.onLink(ev(K::Request, "MODE", "RADAR"), out);
    s.onButton(2, out);
    out.clear(); s.onLink(ev(K::Request, "READY"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "OK"));
    TEST_ASSERT_STATE(ShuttingDown);
    s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
    TEST_ASSERT_FALSE(has(A::Send, "SESSION"));
}

void test_radar_debug_ends_after_60_min()
{
    PiSession s(d); toRunning(s);
    s.onLink(ev(K::Request, "MODE", "RADAR"), out);
    out.clear(); s.onTick(3599999, false, out);
    TEST_ASSERT_FALSE(has(A::Send));
    TEST_ASSERT_STATE(RadarDebug);
    s.onTick(1, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
    TEST_ASSERT_STATE(ShuttingDown);
}

void test_requests_while_starting()
{
    PiSession s(d); s.startHand(out);
    out.clear(); s.onLink(ev(K::Request, "DONE"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "OK"));
    TEST_ASSERT_STATE(Starting);
    out.clear(); s.onLink(ev(K::Request, "MODE", "NORMAL"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "OK"));
    TEST_ASSERT_STATE(Starting);
    s.onTick(0, false, out);
    TEST_ASSERT_FALSE(has(A::Send));
}

void test_mode_normal_in_running_changes_nothing()
{
    PiSession s(d); toRunning(s);
    SessionData before = d;
    s.onLink(ev(K::Request, "MODE", "NORMAL"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "OK"));
    TEST_ASSERT_EQUAL_MEMORY(&before, &d, sizeof d);
}

void test_requests_in_radar_debug()
{
    PiSession s(d); toRunning(s);
    s.onLink(ev(K::Request, "MODE", "RADAR"), out);
    s.onTick(1000, false, out);
    out.clear(); s.onLink(ev(K::Request, "MODE", "RADAR"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "OK"));
    TEST_ASSERT_STATE(RadarDebug);
    TEST_ASSERT_EQUAL_UINT32(1000, d.inStateMs);   // die 60 min beginnen nicht neu
    out.clear(); s.onLink(ev(K::Request, "DONE"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "OK"));
    TEST_ASSERT_STATE(ShuttingDown);
    s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
}

void test_requests_while_shutting_down_and_halting()
{
    const char* const cmds[][2] = {{"READY", ""}, {"DONE", ""}, {"MODE", "NORMAL"}};
    PiSession s(d); toShuttingDown(s);
    for (const auto& c : cmds)
    {
        SessionData before = d;
        out.clear(); s.onLink(ev(K::Request, c[0], c[1]), out);
        TEST_ASSERT_TRUE(has(A::Reply, "OK"));
        TEST_ASSERT_EQUAL_MEMORY(&before, &d, sizeof d);
    }
    s.onLink(ev(K::Response, "OK"), out);
    TEST_ASSERT_STATE(Halting);
    for (const auto& c : cmds)
    {
        SessionData before = d;
        out.clear(); s.onLink(ev(K::Request, c[0], c[1]), out);
        TEST_ASSERT_TRUE(has(A::Reply, "OK"));
        TEST_ASSERT_EQUAL_MEMORY(&before, &d, sizeof d);
    }
}

void test_buttons_in_running_send_button_n_in_order()
{
    PiSession s(d); toRunning(s);
    s.onButton(6, out); s.onButton(5, out);
    TEST_ASSERT_TRUE(out.empty());
    s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "BUTTON", "6"));
    TEST_ASSERT_FALSE(has(A::Send, "BUTTON", "5"));
    s.onLink(ev(K::Response, "OK"), out);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "BUTTON", "5"));
}

void test_button_queue_holds_six_then_logs()
{
    const int keys[] = {1, 3, 4, 5, 6, 1};
    PiSession s(d); toRunning(s);
    for (int k : keys) s.onButton(k, out);
    TEST_ASSERT_TRUE(out.empty());
    s.onButton(3, out);
    TEST_ASSERT_TRUE(has(A::Log));
    TEST_ASSERT_EQUAL_UINT8(6, d.buttonCount);
    for (int k : keys)
    {
        out.clear(); s.onTick(0, false, out);
        const std::string n(1, static_cast<char>('0' + k));
        TEST_ASSERT_TRUE(has(A::Send, "BUTTON", n));
        s.onLink(ev(K::Response, "OK"), out);
    }
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_FALSE(has(A::Send));
}

void test_buttons_ignored_outside_running()
{
    const int keys[] = {1, 3, 4, 5, 6};
    PiSession s(d); s.startHand(out);
    out.clear();
    for (int k : keys) s.onButton(k, out);
    TEST_ASSERT_TRUE(out.empty());
    TEST_ASSERT_EQUAL_UINT8(0, d.buttonCount);

    PiSession::reset(d); toRunning(s);
    s.onLink(ev(K::Request, "MODE", "RADAR"), out);
    out.clear();
    for (int k : keys) s.onButton(k, out);
    TEST_ASSERT_TRUE(out.empty());
    TEST_ASSERT_EQUAL_UINT8(0, d.buttonCount);

    PiSession::reset(d); out.clear(); toShuttingDown(s);
    for (int k : keys) s.onButton(k, out);
    TEST_ASSERT_TRUE(out.empty());
    TEST_ASSERT_EQUAL_UINT8(0, d.buttonCount);

    s.onLink(ev(K::Response, "OK"), out);
    TEST_ASSERT_STATE(Halting);
    out.clear();
    for (int k : keys) s.onButton(k, out);
    TEST_ASSERT_TRUE(out.empty());
    TEST_ASSERT_EQUAL_UINT8(0, d.buttonCount);
}

void test_bt2_while_shutting_down_or_halting_does_nothing()
{
    PiSession s(d); toShuttingDown(s);
    SessionData before = d;
    s.onButton(2, out);
    TEST_ASSERT_TRUE(out.empty());
    TEST_ASSERT_EQUAL_MEMORY(&before, &d, sizeof d);
    s.onLink(ev(K::Response, "OK"), out);
    out.clear(); before = d;
    s.onButton(2, out);
    TEST_ASSERT_TRUE(out.empty());
    TEST_ASSERT_EQUAL_MEMORY(&before, &d, sizeof d);
}

void test_shutdown_drops_queued_buttons()
{
    PiSession s(d); toRunning(s);
    s.onTick(10000, false, out);                   // PING offen
    s.onButton(4, out);
    s.onButton(2, out);
    TEST_ASSERT_EQUAL_UINT8(0, d.buttonCount);
    s.onLink(ev(K::Response, "PONG"), out);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
    TEST_ASSERT_FALSE(has(A::Send, "BUTTON"));
}

void test_repeated_pi_requests_change_nothing()
{
    PiSession s(d); toRunning(s);
    s.onLink(ev(K::Request, "DONE"), out);
    TEST_ASSERT_STATE(ShuttingDown);
    SessionData before = d;
    s.onLink(ev(K::Request, "DONE"), out);
    TEST_ASSERT_EQUAL_MEMORY(&before, &d, sizeof d);
    TEST_ASSERT_EQUAL(2, count(A::Reply, "OK"));
    s.onTick(0, false, out);
    TEST_ASSERT_EQUAL(1, count(A::Send, "SHUTDOWN"));

    PiSession::reset(d); out.clear();              // READY zweimal beim Einschalten
    s.startHand(out);
    s.onLink(ev(K::Request, "READY"), out);
    before = d;
    s.onLink(ev(K::Request, "READY"), out);
    TEST_ASSERT_EQUAL_MEMORY(&before, &d, sizeof d);
    TEST_ASSERT_EQUAL(2, count(A::Reply, "OK"));
    s.onTick(0, false, out);
    TEST_ASSERT_EQUAL(1, count(A::Send, "SESSION"));

    s.onLink(ev(K::Response, "OK"), out);          // MODE zweimal
    s.onLink(ev(K::Request, "MODE", "RADAR"), out);
    before = d;
    s.onLink(ev(K::Request, "MODE", "RADAR"), out);
    TEST_ASSERT_EQUAL_MEMORY(&before, &d, sizeof d);
    s.onLink(ev(K::Request, "MODE", "NORMAL"), out);
    before = d;
    s.onLink(ev(K::Request, "MODE", "NORMAL"), out);
    TEST_ASSERT_EQUAL_MEMORY(&before, &d, sizeof d);
}

void test_resume_after_reset()
{
    {   // SESSION offen
        PiSession s(d); s.startHand(out);
        s.onLink(ev(K::Request, "READY"), out);
        s.onTick(0, false, out);
    }
    out.clear();
    {
        PiSession s(d); s.resume(out);
        TEST_ASSERT_FALSE(has(A::PowerOn));
        TEST_ASSERT_EQUAL(static_cast<int>(Awaiting::None), static_cast<int>(d.awaiting));
        s.onTick(0, false, out);
        TEST_ASSERT_TRUE(has(A::Send, "SESSION", "HAND"));
        TEST_ASSERT_STATE(Running);
    }

    PiSession::reset(d); out.clear();
    {   // SHUTDOWN offen
        PiSession s(d); toShuttingDown(s);
    }
    {
        PiSession s(d); s.resume(out);
        TEST_ASSERT_FALSE(has(A::PowerOn));
        s.onTick(0, false, out);
        TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
        TEST_ASSERT_STATE(ShuttingDown);
    }

    PiSession::reset(d); out.clear();
    {   // PING offen, zwei Aussetzer davor
        PiSession s(d); toRunning(s);
        missPing(s); missPing(s);
        s.onTick(10000, false, out);
    }
    out.clear();
    {
        PiSession s(d); s.resume(out);
        TEST_ASSERT_TRUE(out.empty());
        TEST_ASSERT_EQUAL_UINT8(2, d.missedPings);
        TEST_ASSERT_EQUAL(static_cast<int>(Awaiting::None), static_cast<int>(d.awaiting));
        TEST_ASSERT_STATE(Running);
        s.onTick(10000, false, out);
        TEST_ASSERT_TRUE(has(A::Send, "PING"));
    }

    PiSession::reset(d); out.clear();
    {   // BUTTON offen
        PiSession s(d); toRunning(s);
        s.onButton(3, out);
        s.onTick(0, false, out);
        TEST_ASSERT_TRUE(has(A::Send, "BUTTON", "3"));
    }
    out.clear();
    {
        PiSession s(d); s.resume(out);
        TEST_ASSERT_EQUAL(1, static_cast<int>(out.size()));
        TEST_ASSERT_TRUE(has(A::Log));
        out.clear(); s.onTick(0, false, out);
        TEST_ASSERT_FALSE(has(A::Send));
        TEST_ASSERT_STATE(Running);
    }
}

void test_reset_gives_off_and_inactive()
{
    std::memset(&d, 0xA5, sizeof d);
    PiSession::reset(d);
    PiSession s(d);
    TEST_ASSERT_STATE(Off);
    TEST_ASSERT_FALSE(s.active());
    TEST_ASSERT_EQUAL(static_cast<int>(StartReason::Hand), static_cast<int>(d.reason));
    TEST_ASSERT_EQUAL(static_cast<int>(Awaiting::None), static_cast<int>(d.awaiting));
    TEST_ASSERT_EQUAL_UINT8(0, d.flags);
    TEST_ASSERT_EQUAL_UINT8(0, d.missedPings);
    TEST_ASSERT_EQUAL_UINT8(0, d.buttonCount);
    for (uint8_t b : d.buttons) TEST_ASSERT_EQUAL_UINT8(0, b);
    TEST_ASSERT_EQUAL_UINT32(0, d.inStateMs);
    TEST_ASSERT_EQUAL_UINT32(0, d.sincePingMs);
    TEST_ASSERT_EQUAL_UINT32(0, d.sinceBusyMs);
    TEST_ASSERT_EQUAL_UINT32(0, d.sessionMs);
}

void test_start_only_from_off()
{
    PiSession s(d); toRunning(s);
    s.startHand(out); s.startNight(out);
    TEST_ASSERT_TRUE(out.empty());
    TEST_ASSERT_STATE(Running);

    PiSession::reset(d);                           // AUS: Tasten gehen an die Application
    s.onButton(2, out); s.onButton(1, out);
    s.onTick(60000, false, out);
    TEST_ASSERT_TRUE(out.empty());
    TEST_ASSERT_STATE(Off);
}

void test_new_hand_session_ends_no_answer_text_early()
{
    PiSession s(d); s.startHand(out);
    s.onTick(120000, false, out);                  // hart aus mit Text
    TEST_ASSERT_TRUE(s.active());
    out.clear(); s.startNight(out);
    TEST_ASSERT_TRUE(out.empty());
    s.startHand(out);
    TEST_ASSERT_TRUE(has(A::PowerOn));
    TEST_ASSERT_TRUE(has(A::Show, "PI STARTET"));
    TEST_ASSERT_STATE(Starting);
    TEST_ASSERT_EQUAL_UINT8(0, d.flags);
    out.clear(); s.onTick(10000, false, out);
    TEST_ASSERT_TRUE(out.empty());
}

void test_any_answer_to_ping_resets_missed_pings()
{
    PiSession s(d); toRunning(s);
    missPing(s); missPing(s);
    s.onTick(10000, false, out);
    s.onLink(ev(K::Response, "ERROR", "UNKNOWN"), out);
    TEST_ASSERT_EQUAL_UINT8(0, d.missedPings);
    missPing(s); missPing(s);
    TEST_ASSERT_FALSE(has(A::PowerOff));
}

void test_expired_ping_outside_running_is_not_a_miss()
{
    PiSession s(d); toRunning(s);
    missPing(s); missPing(s);
    s.onTick(10000, false, out);                   // dritter PING offen
    s.onLink(ev(K::Request, "MODE", "RADAR"), out);
    s.onLink(ev(K::Expired, "PING"), out);         // Pi auf 115 200 Baud
    TEST_ASSERT_FALSE(has(A::PowerOff));
    TEST_ASSERT_STATE(RadarDebug);

    PiSession::reset(d); out.clear();
    toRunning(s);
    missPing(s); missPing(s);
    s.onTick(10000, false, out);
    s.onButton(2, out);
    s.onLink(ev(K::Expired, "PING"), out);
    TEST_ASSERT_FALSE(has(A::PowerOff));
    TEST_ASSERT_STATE(ShuttingDown);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
}

void test_answer_without_own_request_is_only_logged()
{
    PiSession s(d); toRunning(s);
    SessionData before = d;
    s.onLink(ev(K::Response, "OK"), out);
    s.onLink(ev(K::Expired, "GET", "QUOTE|"), out);
    TEST_ASSERT_EQUAL(2, static_cast<int>(out.size()));
    TEST_ASSERT_EQUAL(2, count(A::Log));
    TEST_ASSERT_EQUAL_MEMORY(&before, &d, sizeof d);
}

// Daten aus dem RTC-Speicher: MAGIC und CRC stimmen, die Werte trotzdem nicht
void test_valid_rejects_values_outside_the_enums()
{
    TEST_ASSERT_TRUE(PiSession::valid(d));         // nach reset
    PiSession s(d); toRunning(s);
    s.onButton(3, out);
    TEST_ASSERT_TRUE(PiSession::valid(d));

    SessionData edge = SessionData();              // jeweils der groesste gueltige Wert
    edge.state = SessionState::Halting;
    edge.reason = StartReason::Night;
    edge.awaiting = Awaiting::Button;
    edge.buttonCount = 6;
    TEST_ASSERT_TRUE(PiSession::valid(edge));

    SessionData bad = edge; bad.state = static_cast<SessionState>(6);
    TEST_ASSERT_FALSE(PiSession::valid(bad));
    bad = edge; bad.reason = static_cast<StartReason>(2);
    TEST_ASSERT_FALSE(PiSession::valid(bad));
    bad = edge; bad.awaiting = static_cast<Awaiting>(5);
    TEST_ASSERT_FALSE(PiSession::valid(bad));
    bad = edge; bad.buttonCount = 7;
    TEST_ASSERT_FALSE(PiSession::valid(bad));
    std::memset(&bad, 0xA5, sizeof bad);           // Muster, wie es nach dem Einschalten stehen kann
    TEST_ASSERT_FALSE(PiSession::valid(bad));
}

static const unsigned long HUGE_MS = 0xFFFFFFFFUL;

void test_huge_tick_while_starting_still_hard_off()
{
    PiSession s(d); s.startHand(out);
    s.onTick(1, false, out);
    out.clear(); s.onTick(HUGE_MS, false, out);    // 1 + HUGE_MS liefe auf 0 um
    TEST_ASSERT_TRUE(has(A::PowerOff));
    TEST_ASSERT_TRUE(has(A::Show, "PI ANTWORTET NICHT"));
    TEST_ASSERT_STATE(Off);

    s.onTick(1, false, out);                       // die 10 s Text ebenso
    out.clear(); s.onTick(HUGE_MS, false, out);
    TEST_ASSERT_TRUE(has(A::DisplayOff));
    TEST_ASSERT_FALSE(s.active());

    SessionData before = d;                        // ein weiterer grosser Takt aendert nichts
    out.clear(); s.onTick(HUGE_MS, false, out);
    TEST_ASSERT_TRUE(out.empty());
    TEST_ASSERT_EQUAL_MEMORY(&before, &d, sizeof d);
}

void test_huge_ticks_saturate_in_every_state()
{
    PiSession s(d); toRunning(s);                  // BETRIEB: PING-Abstand
    s.onTick(1, true, out);
    for (int i = 0; i < 2; ++i)                    // auch ein zweiter grosser Takt laeuft nicht um
    {
        s.onTick(HUGE_MS, true, out);
        TEST_ASSERT_EQUAL_UINT32(0xFFFFFFFFu, d.sincePingMs);
        TEST_ASSERT_EQUAL_UINT32(0xFFFFFFFFu, d.inStateMs);
        TEST_ASSERT_EQUAL_UINT32(0xFFFFFFFFu, d.sessionMs);
    }
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "PING"));

    PiSession::reset(d); out.clear();              // RADAR-DEBUG: 60 min
    toRunning(s);
    s.onLink(ev(K::Request, "MODE", "RADAR"), out);
    s.onTick(1, false, out);
    s.onTick(HUGE_MS, false, out);
    TEST_ASSERT_STATE(ShuttingDown);

    PiSession::reset(d); out.clear();              // HERUNTERFAHREN: 10 min BUSY
    toShuttingDown(s);
    s.onLink(ev(K::Response, "BUSY"), out);
    s.onTick(1, false, out);
    out.clear(); s.onTick(HUGE_MS, false, out);
    TEST_ASSERT_TRUE(has(A::PowerOff));
    TEST_ASSERT_STATE(Off);

    PiSession::reset(d); out.clear();              // HALT-WARTEN: T_halt
    toShuttingDown(s);
    s.onLink(ev(K::Response, "OK"), out);
    s.onTick(1, false, out);
    out.clear(); s.onTick(HUGE_MS, false, out);
    TEST_ASSERT_TRUE(has(A::PowerOff));
    TEST_ASSERT_STATE(Off);
}

int main(int, char**)
{
    UNITY_BEGIN();
    RUN_TEST(test_ready_replies_ok_then_tick_sends_session_hand);
    RUN_TEST(test_no_ready_within_t_boot_is_hard_off_with_message_for_10_s);
    RUN_TEST(test_night_start_shows_nothing_and_sends_session_nacht);
    RUN_TEST(test_no_ping_while_starting);
    RUN_TEST(test_bt2_while_starting_shuts_down_after_ready_without_session);
    RUN_TEST(test_send_order_session_button_ping);
    RUN_TEST(test_unknown_mode_is_error_unknown);
    RUN_TEST(test_ping_every_10_s);
    RUN_TEST(test_three_missed_pings_hard_off_with_message);
    RUN_TEST(test_pong_resets_missed_pings);
    RUN_TEST(test_ping_waits_while_link_busy);
    RUN_TEST(test_ready_in_running_resends_session);
    RUN_TEST(test_ready_in_radar_debug_returns_to_running);
    RUN_TEST(test_done_starts_shutdown);
    RUN_TEST(test_bt2_in_running_starts_shutdown);
    RUN_TEST(test_shutdown_waits_for_free_link);
    RUN_TEST(test_busy_retries_after_30_s);
    RUN_TEST(test_busy_for_10_min_is_hard_off_without_message);
    RUN_TEST(test_shutdown_expired_is_hard_off_without_message);
    RUN_TEST(test_ok_to_shutdown_shows_text_then_power_off_after_t_halt);
    RUN_TEST(test_night_halting_has_no_display_actions);
    RUN_TEST(test_night_hard_off_leaves_display_alone);
    RUN_TEST(test_session_expired_starts_shutdown);
    RUN_TEST(test_session_answer_other_than_ok_starts_shutdown);
    RUN_TEST(test_session_failure_in_radar_debug_waits_like_bt2);
    RUN_TEST(test_mode_radar_and_normal);
    RUN_TEST(test_nothing_is_sent_in_radar_debug);
    RUN_TEST(test_mode_radar_outside_running_is_error_state);
    RUN_TEST(test_bt2_in_radar_debug_shuts_down_after_mode_normal);
    RUN_TEST(test_ready_in_radar_debug_with_bt2_shuts_down);
    RUN_TEST(test_radar_debug_ends_after_60_min);
    RUN_TEST(test_requests_while_starting);
    RUN_TEST(test_mode_normal_in_running_changes_nothing);
    RUN_TEST(test_requests_in_radar_debug);
    RUN_TEST(test_requests_while_shutting_down_and_halting);
    RUN_TEST(test_buttons_in_running_send_button_n_in_order);
    RUN_TEST(test_button_queue_holds_six_then_logs);
    RUN_TEST(test_buttons_ignored_outside_running);
    RUN_TEST(test_bt2_while_shutting_down_or_halting_does_nothing);
    RUN_TEST(test_shutdown_drops_queued_buttons);
    RUN_TEST(test_repeated_pi_requests_change_nothing);
    RUN_TEST(test_resume_after_reset);
    RUN_TEST(test_reset_gives_off_and_inactive);
    RUN_TEST(test_start_only_from_off);
    RUN_TEST(test_new_hand_session_ends_no_answer_text_early);
    RUN_TEST(test_any_answer_to_ping_resets_missed_pings);
    RUN_TEST(test_expired_ping_outside_running_is_not_a_miss);
    RUN_TEST(test_answer_without_own_request_is_only_logged);
    RUN_TEST(test_valid_rejects_values_outside_the_enums);
    RUN_TEST(test_huge_tick_while_starting_still_hard_off);
    RUN_TEST(test_huge_ticks_saturate_in_every_state);
    return UNITY_END();
}
