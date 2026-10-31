#pragma once
// Sitzung des ESP mit dem Pi: einschalten, PING, Tasten, Zitat der Nacht,
// herunterfahren (Spec 7, 9). Der ganze Zustand liegt in SessionData und
// NightData; nach einem Reset macht eine neue PiSession auf denselben Daten
// weiter. Ohne Arduino; die Application fuehrt die Aktionen aus.
#include <cstdint>
#include <string>
#include <vector>
#include "NightData.h"
#include "PiLink.h"

enum class SessionState : uint8_t { Off = 0, Starting = 1, Running = 2, RadarDebug = 3, ShuttingDown = 4, Halting = 5 };
enum class StartReason : uint8_t { Hand = 0, Night = 1 };
enum class Awaiting : uint8_t { None = 0, Ping = 1, Session = 2, Shutdown = 3, Button = 4, Get = 5 };

// Liegt im RTC-Speicher (Task 4): nur feste Typen, die Zahlenwerte der enums bleiben.
struct SessionData
{
    SessionState state;
    StartReason reason;
    Awaiting awaiting;      // offene eigene Anfrage
    uint8_t flags;          // SessionFlag
    uint8_t missedPings;
    uint8_t buttonCount;
    uint8_t buttons[6];     // Warteschlange (R2)
    uint32_t inStateMs;     // T_boot, T_halt, 60 min Radar, 10 min BUSY, 10 s Text (D18)
    uint32_t sincePingMs;
    uint32_t sinceBusyMs;
    uint32_t sessionMs;     // nur fuers Log (Spec 11 sessionSeconds)
};
static_assert(sizeof(SessionData) == 28, "SessionData liegt im RTC-Speicher");

namespace SessionFlag
{
constexpr uint8_t PendingShutdown = 1;   // BT2 gemerkt (EINSCHALTEN, RADAR-DEBUG)
constexpr uint8_t NeedSession = 2;       // SESSION wartet auf freie Leitung
constexpr uint8_t NeedShutdown = 4;      // SHUTDOWN wartet auf freie Leitung
constexpr uint8_t ShowingNoAnswer = 8;   // PI ANTWORTET NICHT steht noch
}

struct SessionAction
{
    enum class Kind { PowerOn, PowerOff, Send, Reply, Show, DisplayOff, Log, QuoteReady };
    Kind kind;
    std::string command;   // Send/Reply: Befehl; Show/Log/QuoteReady: der Text
    std::string data;      // Send/Reply: Daten
};

// Fristen und Startwerte (Spec 12). Die Frist von SHUTDOWN steht im Codec.
namespace SessionTiming
{
constexpr unsigned long BOOT_MS = 120000;          // T_boot: Einschalten bis READY
constexpr unsigned long PING_INTERVAL_MS = 10000;  // PING-Abstand im Betrieb
constexpr unsigned long PING_MISSES = 3;           // Aussetzer bis hart aus
constexpr unsigned long BUSY_RETRY_MS = 30000;     // SHUTDOWN noch einmal nach BUSY
constexpr unsigned long BUSY_MAX_MS = 600000;      // ab Eintritt in HERUNTERFAHREN
constexpr unsigned long HALT_MS = 30000;           // T_halt, Startwert, wird gemessen
constexpr unsigned long RADAR_MAX_MS = 3600000;    // Radar-Debug hoechstens
constexpr unsigned long NO_ANSWER_MS = 10000;      // PI ANTWORTET NICHT sichtbar (D18)
}

class PiSession
{
public:
    PiSession(SessionData& data, NightData& night);
    static void reset(SessionData& data);                  // Kaltstart: Off, alles 0
    static bool valid(const SessionData& data);            // false: enum ausserhalb seiner Werte, buttonCount > 6
    bool active() const;                                  // nicht Off, oder PI ANTWORTET NICHT noch sichtbar
    void resume(std::vector<SessionAction>& out);          // einmal nach jedem Reset, wenn active() (R8)
    void startHand(std::vector<SessionAction>& out);       // BT2 im Zustand Off
    void startNight(std::vector<SessionAction>& out);      // Mitternacht; danach requestQuote
    // Auftrag der Nacht in dieser Sitzung (M4-a), nur in EINSCHALTEN und BETRIEB.
    // Datum und Vortag setzt die Application vorher. true: neuer Auftrag (Wanted).
    bool requestQuote();
    // Naehme requestQuote den Auftrag jetzt an? Dieselben Bedingungen, ohne etwas zu aendern.
    bool canRequestQuote() const;
    void onButton(int button, std::vector<SessionAction>& out);           // Tabelle 5.2, ausser Off; NACHT: N2, N3
    void onLink(const LinkEvent& event, std::vector<SessionAction>& out); // Antworten sofort als Reply
    void onTick(unsigned long elapsedMs, bool linkBusy, std::vector<SessionAction>& out);  // nur hier Send

private:
    SessionData& m_d;
    NightData& m_n;
};
