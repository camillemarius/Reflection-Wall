#include <unity.h>
#include <cstring>
#include <string>
#include <vector>
#include "PiSession.h"

using K = LinkEvent::Kind;
using A = SessionAction::Kind;

#define TEST_ASSERT_STATE(s) TEST_ASSERT_EQUAL(static_cast<int>(SessionState::s), static_cast<int>(d.state))

static SessionData d;
static NightData n;
static std::vector<SessionAction> out;
static LinkEvent ev(LinkEvent::Kind k, const char* cmd, const char* data = "") {
    LinkEvent e; e.kind = k; e.message.command = cmd; e.message.data = data; return e; }
static bool has(SessionAction::Kind k, const std::string& c = "", const std::string& v = "") {
    for (const auto& a : out) if (a.kind == k && (c.empty() || a.command == c) && (v.empty() || a.data == v)) return true;
    return false; }
void setUp() { PiSession::reset(d); NightJob::reset(n); out.clear(); }
void tearDown() {}

static int count(SessionAction::Kind k, const std::string& c = "")
{
    int hits = 0;
    for (const auto& a : out) if (a.kind == k && (c.empty() || a.command == c)) ++hits;
    return hits;
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

#define TEST_ASSERT_NIGHT(st, res) do { \
    TEST_ASSERT_EQUAL(static_cast<int>(NightStatus::st), static_cast<int>(n.status)); \
    TEST_ASSERT_EQUAL(static_cast<int>(NightResult::res), static_cast<int>(n.result)); } while (0)

static const char* const YESTERDAY = "GESTERN WAR ES KALT";
static const char* const GET_DATA = "QUOTE|GESTERN WAR ES KALT";
static const char* const QUOTE_OK = "DER WEG IST DAS ZIEL";
static const char* const QUOTE_BAD = "ZU VIEL!";      // '!' gehoert nicht zu den Zeichen

// Daten der ersten Aktion mit diesem Befehl, "?" wenn keine da ist
static std::string dataOf(SessionAction::Kind k, const std::string& c)
{
    for (const auto& a : out) if (a.kind == k && a.command == c) return a.data;
    return "?";
}

// BETRIEB (NACHT oder HAND), Auftrag der Nacht gestellt, GET offen
static void toGet(PiSession& s, bool hand = false)
{
    std::strcpy(n.date, "2026-10-26");
    std::strcpy(n.yesterday, YESTERDAY);
    toRunning(s, hand);
    TEST_ASSERT_TRUE(s.requestQuote());
    s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "GET", GET_DATA));
    out.clear();
}

void test_ready_replies_ok_then_tick_sends_session_hand() {
    PiSession s(d, n); s.startHand(out);
    TEST_ASSERT_TRUE(has(SessionAction::Kind::PowerOn));
    TEST_ASSERT_TRUE(has(SessionAction::Kind::Show, "PI STARTET"));
    out.clear(); s.onLink(ev(LinkEvent::Kind::Request, "READY"), out);
    TEST_ASSERT_TRUE(has(SessionAction::Kind::Reply, "OK"));
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(SessionAction::Kind::Send, "SESSION", "HAND"));
    TEST_ASSERT_EQUAL(static_cast<int>(SessionState::Running), static_cast<int>(d.state));
}

void test_no_ready_within_t_boot_is_hard_off_with_message_for_10_s() {
    PiSession s(d, n); s.startHand(out); out.clear();
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
    PiSession s(d, n); s.startNight(out);
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
    PiSession s(d, n); s.startHand(out); out.clear();
    s.onTick(60000, false, out);
    TEST_ASSERT_FALSE(has(A::Send, "PING"));
    TEST_ASSERT_FALSE(has(A::Send));
    TEST_ASSERT_STATE(Starting);
}

void test_bt2_while_starting_shuts_down_after_ready_without_session()
{
    PiSession s(d, n); s.startHand(out);
    s.onButton(2, out);
    TEST_ASSERT_STATE(Starting);
    out.clear(); s.onLink(ev(K::Request, "READY"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "OK"));
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
    TEST_ASSERT_FALSE(has(A::Send, "SESSION"));
    TEST_ASSERT_STATE(ShuttingDown);
    // In der Nacht gilt N3 (test_bt2_at_night_starting_becomes_hand).
}

void test_send_order_session_button_ping()
{
    PiSession s(d, n); toRunning(s);
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
    PiSession s(d, n); toRunning(s);
    SessionData before = d;
    s.onLink(ev(K::Request, "MODE", "FAST"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "ERROR", "UNKNOWN"));
    TEST_ASSERT_EQUAL_MEMORY(&before, &d, sizeof d);
}

void test_ping_every_10_s()
{
    PiSession s(d, n); toRunning(s);
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
    PiSession s(d, n); toRunning(s);
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
    PiSession s(d, n); toRunning(s);
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
    PiSession s(d, n); toRunning(s);
    s.onTick(20000, true, out);
    TEST_ASSERT_FALSE(has(A::Send));
    s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "PING"));
}

void test_ready_in_running_resends_session()
{
    PiSession s(d, n); toRunning(s);
    s.onLink(ev(K::Request, "READY"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "OK"));
    TEST_ASSERT_STATE(Running);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SESSION", "HAND"));
    TEST_ASSERT_STATE(Running);
}

void test_ready_in_radar_debug_returns_to_running()
{
    PiSession s(d, n); toRunning(s);
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
    PiSession s(d, n); toRunning(s);
    s.onLink(ev(K::Request, "DONE"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "OK"));
    TEST_ASSERT_STATE(ShuttingDown);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
}

void test_bt2_in_running_starts_shutdown()
{
    PiSession s(d, n); toRunning(s);
    s.onButton(2, out);
    TEST_ASSERT_STATE(ShuttingDown);
    s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
}

void test_shutdown_waits_for_free_link()
{
    PiSession s(d, n); toRunning(s);
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
    PiSession s(d, n); toShuttingDown(s);
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
    PiSession s(d, n); toShuttingDown(s);
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
    PiSession s(d, n); toShuttingDown(s);
    s.onLink(ev(K::Expired, "SHUTDOWN"), out);
    TEST_ASSERT_TRUE(has(A::PowerOff));
    TEST_ASSERT_TRUE(has(A::DisplayOff));
    TEST_ASSERT_FALSE(has(A::Show));
    TEST_ASSERT_STATE(Off);
    TEST_ASSERT_FALSE(s.active());
}

void test_ok_to_shutdown_shows_text_then_power_off_after_t_halt()
{
    PiSession s(d, n); toShuttingDown(s);
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
    PiSession s(d, n); s.startNight(out);
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
    PiSession s(d, n); s.startNight(out);
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
    PiSession s(d, n); s.startHand(out);
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
    PiSession s(d, n); s.startHand(out);
    s.onLink(ev(K::Request, "READY"), out);
    s.onTick(0, false, out);
    s.onLink(ev(K::Response, "ERROR", "UNKNOWN"), out);
    TEST_ASSERT_STATE(ShuttingDown);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
}

void test_session_failure_in_radar_debug_waits_like_bt2()
{
    PiSession s(d, n); toRunning(s);
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
    PiSession s(d, n); toRunning(s);
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
    PiSession s(d, n); toRunning(s);
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
    PiSession s(d, n); s.startHand(out);
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
    PiSession s(d, n); toRunning(s);
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
    PiSession s(d, n); toRunning(s);
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
    PiSession s(d, n); toRunning(s);
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
    PiSession s(d, n); s.startHand(out);
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
    PiSession s(d, n); toRunning(s);
    SessionData before = d;
    s.onLink(ev(K::Request, "MODE", "NORMAL"), out);
    TEST_ASSERT_TRUE(has(A::Reply, "OK"));
    TEST_ASSERT_EQUAL_MEMORY(&before, &d, sizeof d);
}

void test_requests_in_radar_debug()
{
    PiSession s(d, n); toRunning(s);
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
    PiSession s(d, n); toShuttingDown(s);
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
    PiSession s(d, n); toRunning(s);
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
    PiSession s(d, n); toRunning(s);
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
    PiSession s(d, n); s.startHand(out);
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
    PiSession s(d, n); toShuttingDown(s);
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
    PiSession s(d, n); toRunning(s);
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
    PiSession s(d, n); toRunning(s);
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
        PiSession s(d, n); s.startHand(out);
        s.onLink(ev(K::Request, "READY"), out);
        s.onTick(0, false, out);
    }
    out.clear();
    {
        PiSession s(d, n); s.resume(out);
        TEST_ASSERT_FALSE(has(A::PowerOn));
        TEST_ASSERT_EQUAL(static_cast<int>(Awaiting::None), static_cast<int>(d.awaiting));
        s.onTick(0, false, out);
        TEST_ASSERT_TRUE(has(A::Send, "SESSION", "HAND"));
        TEST_ASSERT_STATE(Running);
    }

    PiSession::reset(d); out.clear();
    {   // SHUTDOWN offen
        PiSession s(d, n); toShuttingDown(s);
    }
    {
        PiSession s(d, n); s.resume(out);
        TEST_ASSERT_FALSE(has(A::PowerOn));
        s.onTick(0, false, out);
        TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
        TEST_ASSERT_STATE(ShuttingDown);
    }

    PiSession::reset(d); out.clear();
    {   // PING offen, zwei Aussetzer davor
        PiSession s(d, n); toRunning(s);
        missPing(s); missPing(s);
        s.onTick(10000, false, out);
    }
    out.clear();
    {
        PiSession s(d, n); s.resume(out);
        TEST_ASSERT_TRUE(out.empty());
        TEST_ASSERT_EQUAL_UINT8(2, d.missedPings);
        TEST_ASSERT_EQUAL(static_cast<int>(Awaiting::None), static_cast<int>(d.awaiting));
        TEST_ASSERT_STATE(Running);
        s.onTick(10000, false, out);
        TEST_ASSERT_TRUE(has(A::Send, "PING"));
    }

    PiSession::reset(d); out.clear();
    {   // BUTTON offen
        PiSession s(d, n); toRunning(s);
        s.onButton(3, out);
        s.onTick(0, false, out);
        TEST_ASSERT_TRUE(has(A::Send, "BUTTON", "3"));
    }
    out.clear();
    {
        PiSession s(d, n); s.resume(out);
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
    PiSession s(d, n);
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
    PiSession s(d, n); toRunning(s);
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
    PiSession s(d, n); s.startHand(out);
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
    PiSession s(d, n); toRunning(s);
    missPing(s); missPing(s);
    s.onTick(10000, false, out);
    s.onLink(ev(K::Response, "ERROR", "UNKNOWN"), out);
    TEST_ASSERT_EQUAL_UINT8(0, d.missedPings);
    missPing(s); missPing(s);
    TEST_ASSERT_FALSE(has(A::PowerOff));
}

void test_expired_ping_outside_running_is_not_a_miss()
{
    PiSession s(d, n); toRunning(s);
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
    PiSession s(d, n); toRunning(s);
    SessionData before = d;
    s.onLink(ev(K::Response, "OK"), out);
    s.onLink(ev(K::Expired, "GET", "QUOTE|"), out);
    TEST_ASSERT_EQUAL(2, static_cast<int>(out.size()));
    TEST_ASSERT_EQUAL(2, count(A::Log));
    TEST_ASSERT_EQUAL_MEMORY(&before, &d, sizeof d);
}

// M-2: Geht ein Send nicht raus, meldet die Application der Sitzung gleich
// eine Frist fuer diesen Befehl. Danach ist awaiting frei, und es geht weiter.
void test_expired_right_after_send_frees_awaiting()
{
    PiSession s(d, n); toRunning(s);
    s.onButton(6, out); s.onButton(5, out);
    s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "BUTTON", "6"));
    TEST_ASSERT_EQUAL(static_cast<int>(Awaiting::Button), static_cast<int>(d.awaiting));
    out.clear(); s.onLink(ev(K::Expired, "BUTTON", "6"), out);
    TEST_ASSERT_EQUAL(static_cast<int>(Awaiting::None), static_cast<int>(d.awaiting));
    TEST_ASSERT_FALSE(has(A::Send));
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "BUTTON", "5"));
}

// Daten aus dem RTC-Speicher: MAGIC und CRC stimmen, die Werte trotzdem nicht
void test_valid_rejects_values_outside_the_enums()
{
    TEST_ASSERT_TRUE(PiSession::valid(d));         // nach reset
    PiSession s(d, n); toRunning(s);
    s.onButton(3, out);
    TEST_ASSERT_TRUE(PiSession::valid(d));

    SessionData edge = SessionData();              // jeweils der groesste gueltige Wert
    edge.state = SessionState::Halting;
    edge.reason = StartReason::Night;
    edge.awaiting = Awaiting::Get;
    edge.buttonCount = 6;
    TEST_ASSERT_TRUE(PiSession::valid(edge));

    SessionData bad = edge; bad.state = static_cast<SessionState>(6);
    TEST_ASSERT_FALSE(PiSession::valid(bad));
    bad = edge; bad.reason = static_cast<StartReason>(2);
    TEST_ASSERT_FALSE(PiSession::valid(bad));
    bad = edge; bad.awaiting = static_cast<Awaiting>(6);
    TEST_ASSERT_FALSE(PiSession::valid(bad));
    bad = edge; bad.buttonCount = 7;
    TEST_ASSERT_FALSE(PiSession::valid(bad));
    std::memset(&bad, 0xA5, sizeof bad);           // Muster, wie es nach dem Einschalten stehen kann
    TEST_ASSERT_FALSE(PiSession::valid(bad));
}

static const unsigned long HUGE_MS = 0xFFFFFFFFUL;

void test_huge_tick_while_starting_still_hard_off()
{
    PiSession s(d, n); s.startHand(out);
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
    PiSession s(d, n); toRunning(s);                  // BETRIEB: PING-Abstand
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

// ---------- Nacht (Teil 3b) ----------

void test_night_sends_get_after_session()
{
    std::strcpy(n.yesterday, YESTERDAY);
    PiSession s(d, n); s.startNight(out);
    TEST_ASSERT_TRUE(s.requestQuote());
    out.clear(); s.onTick(0, false, out);          // EINSCHALTEN: noch kein GET
    TEST_ASSERT_FALSE(has(A::Send));
    s.onLink(ev(K::Request, "READY"), out);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_EQUAL(1, count(A::Send));
    TEST_ASSERT_TRUE(has(A::Send, "SESSION", "NACHT"));
    s.onLink(ev(K::Response, "OK"), out);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_EQUAL(1, count(A::Send));
    TEST_ASSERT_EQUAL_STRING(GET_DATA, dataOf(A::Send, "GET").c_str());
    TEST_ASSERT_EQUAL(static_cast<int>(Awaiting::Get), static_cast<int>(d.awaiting));

    PiSession::reset(d); NightJob::reset(n); out.clear();   // ohne Vortag: neue Kette
    toRunning(s, false);
    s.requestQuote();
    s.onTick(0, false, out);
    TEST_ASSERT_EQUAL_STRING("QUOTE|", dataOf(A::Send, "GET").c_str());
}

void test_get_waits_for_buttons()
{
    PiSession s(d, n); toRunning(s);
    std::strcpy(n.yesterday, YESTERDAY);
    s.onTick(10000, true, out);                    // PING faellig, Leitung belegt
    s.onButton(3, out);
    s.onLink(ev(K::Request, "READY"), out);        // SESSION wartet
    TEST_ASSERT_TRUE(s.requestQuote());
    const char* const order[][4] = {{"SESSION", "HAND", "OK", ""}, {"BUTTON", "3", "OK", ""},
                                    {"GET", GET_DATA, "QUOTE", QUOTE_OK}, {"PING", "", "PONG", ""}};
    for (const auto& o : order)
    {
        out.clear(); s.onTick(0, false, out);
        TEST_ASSERT_EQUAL(1, count(A::Send));
        TEST_ASSERT_TRUE(has(A::Send, o[0], o[1]));
        s.onLink(ev(K::Response, o[2], o[3]), out);
    }
    TEST_ASSERT_NIGHT(Got, Ok);
}

void test_no_ping_while_get_open()
{
    PiSession s(d, n); toGet(s);                   // NACHT
    s.onTick(119999, false, out);
    TEST_ASSERT_FALSE(has(A::Send));
    TEST_ASSERT_EQUAL_UINT8(0, d.missedPings);
    TEST_ASSERT_STATE(Running);

    PiSession::reset(d); NightJob::reset(n); out.clear();   // HAND: nach der Antwort gleich PING
    toGet(s, true);
    s.onTick(30000, false, out);
    TEST_ASSERT_FALSE(has(A::Send));
    s.onLink(ev(K::Response, "QUOTE", QUOTE_OK), out);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_EQUAL(1, count(A::Send));
    TEST_ASSERT_TRUE(has(A::Send, "PING"));
}

void test_valid_quote_sets_got_emits_ready_and_shuts_down_at_night()
{
    std::memset(n.quote, 'X', sizeof n.quote - 1);  // altes, laengeres Zitat
    PiSession s(d, n); toGet(s);
    s.onLink(ev(K::Response, "QUOTE", QUOTE_OK), out);
    TEST_ASSERT_NIGHT(Got, Ok);
    TEST_ASSERT_EQUAL_STRING(QUOTE_OK, n.quote);
    TEST_ASSERT_EQUAL_STRING("2026-10-26", n.doneDate);
    TEST_ASSERT_EQUAL_UINT8(1, n.pendingWrite);
    TEST_ASSERT_EQUAL_UINT8(0, n.rejects);
    TEST_ASSERT_EQUAL(1, count(A::QuoteReady));
    TEST_ASSERT_TRUE(has(A::QuoteReady, QUOTE_OK));
    TEST_ASSERT_STATE(ShuttingDown);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_EQUAL(1, count(A::Send));
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
    s.onLink(ev(K::Response, "OK"), out);
    s.onTick(30000, false, out);
    TEST_ASSERT_STATE(Off);
    TEST_ASSERT_FALSE(has(A::Show));
    TEST_ASSERT_FALSE(has(A::DisplayOff));
    TEST_ASSERT_NIGHT(Got, Ok);                     // das Ende der Sitzung aendert nichts mehr
    TEST_ASSERT_TRUE(NightJob::valid(n));
}

void test_valid_quote_in_hand_session_keeps_session()
{
    PiSession s(d, n); toGet(s, true);
    s.onLink(ev(K::Response, "QUOTE", QUOTE_OK), out);
    TEST_ASSERT_NIGHT(Got, Ok);
    TEST_ASSERT_EQUAL_UINT8(1, n.pendingWrite);
    TEST_ASSERT_TRUE(has(A::QuoteReady, QUOTE_OK));
    TEST_ASSERT_FALSE(has(A::Show));
    TEST_ASSERT_STATE(Running);
    out.clear(); s.onTick(10000, false, out);
    TEST_ASSERT_EQUAL(1, count(A::Send));
    TEST_ASSERT_TRUE(has(A::Send, "PING"));
    TEST_ASSERT_STATE(Running);
}

void test_three_rejects_fail_and_shut_down()
{
    const std::string tooLong(97, 'A');
    const char* const bad[] = {QUOTE_BAD, "", tooLong.c_str()};
    PiSession s(d, n); toGet(s);
    for (int i = 0; i < 2; ++i)
    {
        s.onLink(ev(K::Response, "QUOTE", bad[i]), out);
        TEST_ASSERT_EQUAL_UINT8(i + 1, n.rejects);
        TEST_ASSERT_NIGHT(Wanted, None);
        TEST_ASSERT_FALSE(has(A::QuoteReady));
        TEST_ASSERT_STATE(Running);
        out.clear(); s.onTick(0, false, out);      // noch einmal (Z6)
        TEST_ASSERT_EQUAL(1, count(A::Send));
        TEST_ASSERT_TRUE(has(A::Send, "GET", GET_DATA));
        out.clear();
    }
    s.onLink(ev(K::Response, "QUOTE", bad[2]), out);
    TEST_ASSERT_EQUAL_UINT8(3, n.rejects);
    TEST_ASSERT_NIGHT(Failed, Rejected);
    TEST_ASSERT_EQUAL_UINT8(0, n.pendingWrite);
    TEST_ASSERT_FALSE(has(A::QuoteReady));
    TEST_ASSERT_STATE(ShuttingDown);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_EQUAL(1, count(A::Send));
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
    TEST_ASSERT_TRUE(NightJob::valid(n));

    PiSession::reset(d); NightJob::reset(n); out.clear();   // HAND: die Sitzung bleibt
    toGet(s, true);
    for (int i = 0; i < 3; ++i)
    {
        s.onLink(ev(K::Response, "QUOTE", QUOTE_BAD), out);
        s.onTick(0, false, out);
    }
    TEST_ASSERT_NIGHT(Failed, Rejected);
    TEST_ASSERT_EQUAL(2, count(A::Send, "GET"));
    TEST_ASSERT_STATE(Running);
}

void test_error_answer_fails()
{
    const char* const answers[][2] = {{"ERROR", "KI"}, {"ERROR", "ZU_LANG"}, {"OK", ""}};
    PiSession s(d, n);
    for (const auto& a : answers)
    {
        PiSession::reset(d); NightJob::reset(n); out.clear();
        toGet(s);
        s.onLink(ev(K::Response, a[0], a[1]), out);
        TEST_ASSERT_NIGHT(Failed, Error);
        TEST_ASSERT_STATE(ShuttingDown);
        out.clear(); s.onTick(0, false, out);
        TEST_ASSERT_EQUAL(1, count(A::Send));
        TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
    }

    PiSession::reset(d); NightJob::reset(n); out.clear();   // HAND: die Sitzung bleibt
    toGet(s, true);
    s.onLink(ev(K::Response, "ERROR", "BAD_GET"), out);
    TEST_ASSERT_NIGHT(Failed, Error);
    TEST_ASSERT_STATE(Running);
    out.clear(); s.onTick(10000, false, out);
    TEST_ASSERT_EQUAL(1, count(A::Send));
    TEST_ASSERT_TRUE(has(A::Send, "PING"));
}

void test_get_expired_fails()
{
    PiSession s(d, n); toGet(s);
    s.onLink(ev(K::Expired, "GET", GET_DATA), out);
    TEST_ASSERT_NIGHT(Failed, NoAnswer);
    TEST_ASSERT_STATE(ShuttingDown);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_EQUAL(1, count(A::Send));
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));

    PiSession::reset(d); NightJob::reset(n); out.clear();   // HAND: die Sitzung bleibt
    toGet(s, true);
    s.onLink(ev(K::Expired, "GET", GET_DATA), out);
    TEST_ASSERT_NIGHT(Failed, NoAnswer);
    TEST_ASSERT_STATE(Running);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_FALSE(has(A::Send));
}

void test_reset_while_get_open_resends_without_counting()
{
    {   // eine Ablehnung, dann GET zum zweiten Mal offen
        PiSession s(d, n); toGet(s);
        s.onLink(ev(K::Response, "QUOTE", QUOTE_BAD), out);
        s.onTick(0, false, out);
        TEST_ASSERT_EQUAL(static_cast<int>(Awaiting::Get), static_cast<int>(d.awaiting));
    }
    out.clear();
    {
        PiSession s(d, n); s.resume(out);
        TEST_ASSERT_TRUE(out.empty());
        TEST_ASSERT_EQUAL(static_cast<int>(Awaiting::None), static_cast<int>(d.awaiting));
        TEST_ASSERT_EQUAL_UINT8(1, n.rejects);
        TEST_ASSERT_NIGHT(Wanted, None);
        s.onTick(0, false, out);
        TEST_ASSERT_EQUAL(1, count(A::Send));
        TEST_ASSERT_TRUE(has(A::Send, "GET", GET_DATA));
        s.onLink(ev(K::Response, "QUOTE", QUOTE_OK), out);
        TEST_ASSERT_NIGHT(Got, Ok);
        TEST_ASSERT_EQUAL_UINT8(1, n.rejects);
    }
}

void test_session_end_while_wanted_records_reason()
{
    PiSession s(d, n); s.startNight(out);          // kein READY
    TEST_ASSERT_TRUE(s.requestQuote());
    s.onTick(120000, false, out);
    TEST_ASSERT_STATE(Off);
    TEST_ASSERT_NIGHT(Failed, NoReady);

    PiSession::reset(d); NightJob::reset(n); out.clear();   // drei PING-Aussetzer
    toRunning(s);
    missPing(s); missPing(s);
    s.onTick(10000, false, out);                   // dritter PING offen
    TEST_ASSERT_TRUE(s.requestQuote());
    s.onLink(ev(K::Expired, "PING"), out);
    TEST_ASSERT_STATE(Off);
    TEST_ASSERT_NIGHT(Failed, NoAnswer);

    PiSession::reset(d); NightJob::reset(n); out.clear();   // DONE vor dem GET
    toRunning(s, false);
    TEST_ASSERT_TRUE(s.requestQuote());
    s.onLink(ev(K::Request, "DONE"), out);
    s.onTick(0, false, out);
    TEST_ASSERT_FALSE(has(A::Send, "GET"));
    s.onLink(ev(K::Response, "OK"), out);
    TEST_ASSERT_NIGHT(Wanted, None);
    s.onTick(30000, false, out);
    TEST_ASSERT_STATE(Off);
    TEST_ASSERT_NIGHT(Failed, SessionEnded);

    PiSession::reset(d); NightJob::reset(n); out.clear();   // SHUTDOWN ohne Antwort
    toRunning(s, false);
    TEST_ASSERT_TRUE(s.requestQuote());
    n.result = NightResult::StoreFailed;           // ein Grund steht schon: er bleibt
    s.onLink(ev(K::Request, "DONE"), out);
    s.onTick(0, false, out);
    s.onLink(ev(K::Expired, "SHUTDOWN"), out);
    TEST_ASSERT_STATE(Off);
    TEST_ASSERT_NIGHT(Failed, StoreFailed);
}

void test_bt2_at_night_running_becomes_hand_after_get()
{
    PiSession s(d, n); toGet(s);                   // NACHT, GET offen
    s.onButton(2, out);
    TEST_ASSERT_EQUAL(1, static_cast<int>(out.size()));
    TEST_ASSERT_TRUE(has(A::Show, "PI STARTET"));
    TEST_ASSERT_EQUAL(static_cast<int>(StartReason::Hand), static_cast<int>(d.reason));
    TEST_ASSERT_STATE(Running);
    out.clear(); s.onTick(0, true, out);
    s.onTick(0, false, out);
    TEST_ASSERT_FALSE(has(A::Send));               // SESSION wartet auf die Antwort
    s.onLink(ev(K::Response, "QUOTE", QUOTE_OK), out);
    TEST_ASSERT_NIGHT(Got, Ok);
    TEST_ASSERT_TRUE(has(A::QuoteReady, QUOTE_OK));
    TEST_ASSERT_STATE(Running);                    // HAND: kein Herunterfahren
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_EQUAL(1, count(A::Send));
    TEST_ASSERT_TRUE(has(A::Send, "SESSION", "HAND"));
    s.onLink(ev(K::Response, "OK"), out);

    s.onButton(2, out);                            // ab jetzt die Regeln von HAND
    TEST_ASSERT_STATE(ShuttingDown);
    s.onTick(0, false, out);
    s.onLink(ev(K::Response, "OK"), out);
    TEST_ASSERT_TRUE(has(A::Show, "PI FAEHRT HERUNTER"));
    s.onTick(30000, false, out);
    TEST_ASSERT_STATE(Off);
    TEST_ASSERT_NIGHT(Got, Ok);                    // das Zitat zaehlt (N3)
}

// So laeuft N3 auf dem Geraet: BT2 setzt den ESP zurueck, Application::run ruft resume()
// vor handleInput. resume() verwirft das offene GET; SESSION|HAND geht zuerst, dann das GET
// noch einmal (eine neue Anfrage: PiLink gibt ihr eine neue Nummer). Der Pi gibt es dem
// Arbeits-Thread, der noch rechnet, oder antwortet aus dem Ergebnis, das er schon hat.
void test_bt2_at_night_with_get_open_after_reset_sends_hand_then_get_again()
{
    { PiSession before(d, n); toGet(before); }     // NACHT, GET offen; dann der Reset
    PiSession s(d, n);
    s.resume(out);
    TEST_ASSERT_TRUE(out.empty());
    TEST_ASSERT_EQUAL(static_cast<int>(Awaiting::None), static_cast<int>(d.awaiting));
    TEST_ASSERT_NIGHT(Wanted, None);
    s.onButton(2, out);
    TEST_ASSERT_EQUAL(1, static_cast<int>(out.size()));
    TEST_ASSERT_TRUE(has(A::Show, "PI STARTET"));
    TEST_ASSERT_EQUAL(static_cast<int>(StartReason::Hand), static_cast<int>(d.reason));
    TEST_ASSERT_STATE(Running);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_EQUAL(1, count(A::Send));
    TEST_ASSERT_TRUE(has(A::Send, "SESSION", "HAND"));   // zuerst
    s.onLink(ev(K::Response, "OK"), out);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_EQUAL(1, count(A::Send));
    TEST_ASSERT_TRUE(has(A::Send, "GET", GET_DATA));      // dann das GET noch einmal
    TEST_ASSERT_EQUAL_UINT8(0, n.rejects);                 // der Reset zaehlt nicht als Ablehnung
    s.onLink(ev(K::Response, "QUOTE", QUOTE_OK), out);
    TEST_ASSERT_NIGHT(Got, Ok);
    TEST_ASSERT_TRUE(has(A::QuoteReady, QUOTE_OK));
    TEST_ASSERT_EQUAL(static_cast<int>(StartReason::Hand), static_cast<int>(d.reason));
    TEST_ASSERT_STATE(Running);                    // HAND: kein Herunterfahren
    out.clear(); s.onTick(30000, false, out);
    TEST_ASSERT_FALSE(has(A::Send, "SHUTDOWN"));
    TEST_ASSERT_FALSE(has(A::PowerOff));
    TEST_ASSERT_STATE(Running);
}

void test_bt2_at_night_starting_becomes_hand()
{
    PiSession s(d, n); s.startNight(out);
    TEST_ASSERT_TRUE(s.requestQuote());
    out.clear(); s.onButton(2, out);
    TEST_ASSERT_EQUAL(1, static_cast<int>(out.size()));
    TEST_ASSERT_TRUE(has(A::Show, "PI STARTET"));
    TEST_ASSERT_EQUAL(static_cast<int>(StartReason::Hand), static_cast<int>(d.reason));
    TEST_ASSERT_EQUAL_UINT8(0, d.flags);           // kein gemerktes Herunterfahren
    TEST_ASSERT_STATE(Starting);
    s.onLink(ev(K::Request, "READY"), out);
    out.clear(); s.onTick(0, false, out);
    TEST_ASSERT_EQUAL(1, count(A::Send));
    TEST_ASSERT_TRUE(has(A::Send, "SESSION", "HAND"));
    TEST_ASSERT_STATE(Running);
    s.onLink(ev(K::Response, "OK"), out);
    out.clear(); s.onTick(0, false, out);          // das Zitat holt der ESP weiter (M4-a)
    TEST_ASSERT_TRUE(has(A::Send, "GET"));
}

void test_other_buttons_at_night_do_nothing()
{
    const int keys[] = {1, 3, 4, 5, 6};
    const int all[] = {1, 2, 3, 4, 5, 6};
    PiSession s(d, n); s.startNight(out);          // EINSCHALTEN
    out.clear();
    SessionData before = d;
    for (int k : keys) s.onButton(k, out);
    TEST_ASSERT_TRUE(out.empty());
    TEST_ASSERT_EQUAL_MEMORY(&before, &d, sizeof d);

    PiSession::reset(d); out.clear();              // BETRIEB: nichts in die Schlange
    toRunning(s, false);
    before = d;
    for (int k : keys) s.onButton(k, out);
    TEST_ASSERT_TRUE(out.empty());
    TEST_ASSERT_EQUAL_MEMORY(&before, &d, sizeof d);
    s.onTick(0, false, out);
    TEST_ASSERT_FALSE(has(A::Send));

    s.onLink(ev(K::Request, "DONE"), out);         // HERUNTERFAHREN: auch BT2 nichts
    s.onTick(0, false, out);
    TEST_ASSERT_TRUE(has(A::Send, "SHUTDOWN"));
    out.clear(); before = d;
    for (int k : all) s.onButton(k, out);
    TEST_ASSERT_TRUE(out.empty());
    TEST_ASSERT_EQUAL_MEMORY(&before, &d, sizeof d);

    s.onLink(ev(K::Response, "OK"), out);          // HALT-WARTEN
    TEST_ASSERT_STATE(Halting);
    out.clear(); before = d;
    for (int k : all) s.onButton(k, out);
    TEST_ASSERT_TRUE(out.empty());
    TEST_ASSERT_EQUAL_MEMORY(&before, &d, sizeof d);
}

void test_request_quote_only_in_starting_or_running()
{
    std::strcpy(n.date, "2026-10-26");
    std::strcpy(n.doneDate, "2026-10-25");
    std::strcpy(n.yesterday, YESTERDAY);
    n.attempts = 2;
    NightData before = n;
    PiSession s(d, n);
    TEST_ASSERT_FALSE(s.requestQuote());           // AUS
    TEST_ASSERT_EQUAL_MEMORY(&before, &n, sizeof n);

    s.startNight(out);                             // EINSCHALTEN, nach einem Fehlversuch
    n.status = NightStatus::Failed;
    n.rejects = 3;
    n.result = NightResult::Rejected;
    TEST_ASSERT_TRUE(s.requestQuote());
    TEST_ASSERT_NIGHT(Wanted, None);
    TEST_ASSERT_EQUAL_UINT8(0, n.rejects);
    TEST_ASSERT_EQUAL_UINT8(2, n.attempts);
    TEST_ASSERT_EQUAL_STRING("2026-10-26", n.date);
    TEST_ASSERT_EQUAL_STRING("2026-10-25", n.doneDate);
    TEST_ASSERT_EQUAL_STRING(YESTERDAY, n.yesterday);
    before = n;
    TEST_ASSERT_FALSE(s.requestQuote());           // laeuft schon
    TEST_ASSERT_EQUAL_MEMORY(&before, &n, sizeof n);

    PiSession::reset(d); toRunning(s);             // BETRIEB
    n.status = NightStatus::Got;
    before = n;
    TEST_ASSERT_FALSE(s.requestQuote());           // Zitat schon da
    TEST_ASSERT_EQUAL_MEMORY(&before, &n, sizeof n);
    n.status = NightStatus::Idle;
    TEST_ASSERT_TRUE(s.requestQuote());
    TEST_ASSERT_NIGHT(Wanted, None);

    n.status = NightStatus::Idle;                  // RADAR-DEBUG, HERUNTERFAHREN, HALT-WARTEN
    before = n;
    s.onLink(ev(K::Request, "MODE", "RADAR"), out);
    TEST_ASSERT_STATE(RadarDebug);
    TEST_ASSERT_FALSE(s.requestQuote());
    PiSession::reset(d); out.clear(); toShuttingDown(s);
    TEST_ASSERT_FALSE(s.requestQuote());
    s.onLink(ev(K::Response, "OK"), out);
    TEST_ASSERT_STATE(Halting);
    TEST_ASSERT_FALSE(s.requestQuote());
    TEST_ASSERT_EQUAL_MEMORY(&before, &n, sizeof n);
}

// Die Abfrage sagt in jedem Zustand und Status dasselbe wie
// requestQuote und aendert dabei nichts
static void checkCanRequest(PiSession& s, bool stateTakes)
{
    const PiSession& c = s;
    const NightStatus all[] = {NightStatus::Idle, NightStatus::Failed,
                               NightStatus::Wanted, NightStatus::Got};
    for (NightStatus st : all)
    {
        n.status = st;
        const NightData nb = n;
        const SessionData db = d;
        const bool expected = stateTakes && (st == NightStatus::Idle || st == NightStatus::Failed);
        TEST_ASSERT_EQUAL(expected, c.canRequestQuote());
        TEST_ASSERT_EQUAL_MEMORY(&nb, &n, sizeof n);
        TEST_ASSERT_EQUAL_MEMORY(&db, &d, sizeof d);
        TEST_ASSERT_EQUAL(expected, s.requestQuote());
    }
}

void test_can_request_quote_matches_request_quote()
{
    std::strcpy(n.date, "2026-10-26");
    PiSession s(d, n);
    checkCanRequest(s, false);                     // AUS
    s.startNight(out);
    checkCanRequest(s, true);                      // EINSCHALTEN
    PiSession::reset(d); toRunning(s);
    checkCanRequest(s, true);                      // BETRIEB
    n.status = NightStatus::Idle;
    s.onLink(ev(K::Request, "MODE", "RADAR"), out);
    TEST_ASSERT_STATE(RadarDebug);
    checkCanRequest(s, false);
    PiSession::reset(d); out.clear(); toShuttingDown(s);
    checkCanRequest(s, false);                     // HERUNTERFAHREN
    s.onLink(ev(K::Response, "OK"), out);
    TEST_ASSERT_STATE(Halting);
    checkCanRequest(s, false);                     // HALT-WARTEN
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
    RUN_TEST(test_expired_right_after_send_frees_awaiting);
    RUN_TEST(test_valid_rejects_values_outside_the_enums);
    RUN_TEST(test_huge_tick_while_starting_still_hard_off);
    RUN_TEST(test_huge_ticks_saturate_in_every_state);
    RUN_TEST(test_night_sends_get_after_session);
    RUN_TEST(test_get_waits_for_buttons);
    RUN_TEST(test_no_ping_while_get_open);
    RUN_TEST(test_valid_quote_sets_got_emits_ready_and_shuts_down_at_night);
    RUN_TEST(test_valid_quote_in_hand_session_keeps_session);
    RUN_TEST(test_three_rejects_fail_and_shut_down);
    RUN_TEST(test_error_answer_fails);
    RUN_TEST(test_get_expired_fails);
    RUN_TEST(test_reset_while_get_open_resends_without_counting);
    RUN_TEST(test_session_end_while_wanted_records_reason);
    RUN_TEST(test_bt2_at_night_running_becomes_hand_after_get);
    RUN_TEST(test_bt2_at_night_with_get_open_after_reset_sends_hand_then_get_again);
    RUN_TEST(test_bt2_at_night_starting_becomes_hand);
    RUN_TEST(test_other_buttons_at_night_do_nothing);
    RUN_TEST(test_request_quote_only_in_starting_or_running);
    RUN_TEST(test_can_request_quote_matches_request_quote);
    return UNITY_END();
}
