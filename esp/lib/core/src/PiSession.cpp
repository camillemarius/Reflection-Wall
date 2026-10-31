#include "PiSession.h"
#include <cstring>
#include "QuoteCheck.h"

static_assert(QuoteCheck::MAX_CHARS < sizeof(NightData::quote), "ein Zitat passt mit NUL in NightData");

using namespace SessionTiming;
using namespace SessionFlag;
using Kind = SessionAction::Kind;
using Out = std::vector<SessionAction>;

namespace
{
const char* const TEXT_STARTING = "PI STARTET";
const char* const TEXT_HALTING = "PI FAEHRT HERUNTER";
const char* const TEXT_NO_ANSWER = "PI ANTWORTET NICHT";

void emit(Out& out, Kind kind, const std::string& command = std::string(),
          const std::string& data = std::string())
{
    SessionAction a;
    a.kind = kind;
    a.command = command;
    a.data = data;
    out.push_back(a);
}

std::string number(uint32_t v)
{
    std::string s;
    do
    {
        s.insert(s.begin(), static_cast<char>('0' + v % 10));
        v /= 10;
    } while (v != 0);
    return s;
}

bool isSet(const SessionData& d, uint8_t flag) { return (d.flags & flag) != 0; }

// Text aus dem RTC-Speicher, auch ohne NUL nie ueber das Feld hinaus
std::string field(const char* text, std::size_t size)
{
    const void* end = std::memchr(text, '\0', size);
    return std::string(text, end ? static_cast<std::size_t>(static_cast<const char*>(end) - text) : size);
}

// Die Zeitzaehler bleiben beim groessten Wert stehen, statt unter eine Frist
// zurueckzulaufen. Ein unsigned long mit 64 Bit wird ebenso begrenzt.
constexpr uint32_t MS_MAX = 0xFFFFFFFFu;

uint32_t toMs(unsigned long ms)
{
    const uint32_t v = static_cast<uint32_t>(ms);
    return static_cast<unsigned long>(v) == ms ? v : MS_MAX;
}

void addMs(uint32_t& counter, uint32_t dt)
{
    counter = counter > MS_MAX - dt ? MS_MAX : counter + dt;
}

void start(SessionData& d, StartReason reason, Out& out)
{
    PiSession::reset(d);
    d.state = SessionState::Starting;
    d.reason = reason;
    emit(out, Kind::PowerOn);
    if (reason == StartReason::Hand) emit(out, Kind::Show, TEXT_STARTING);
}

// Fehlt das Zitat noch, ist der Versuch gescheitert (M4-a); ein schon
// gemerkter Grund bleibt.
void goOff(SessionData& d, NightData& n, NightResult why, Out& out)
{
    if (n.status == NightStatus::Wanted)
    {
        n.status = NightStatus::Failed;
        if (n.result == NightResult::None) n.result = why;
    }
    emit(out, Kind::Log, "Sitzung aus nach " + number(d.sessionMs / 1000) + " s");
    d.state = SessionState::Off;
    d.awaiting = Awaiting::None;
    d.flags &= ShowingNoAnswer;
    d.buttonCount = 0;
    d.inStateMs = 0;
}

// Speisung trennen ohne Herunterfahren. Text nur bei HAND (R4), in der Nacht
// bleibt die Anzeige, wie sie ist (V1).
void hardOff(SessionData& d, NightData& n, bool message, const char* why, NightResult night, Out& out)
{
    emit(out, Kind::PowerOff);
    emit(out, Kind::Log, std::string("hart aus: ") + why);
    if (d.reason == StartReason::Hand)
    {
        if (message)
        {
            emit(out, Kind::Show, TEXT_NO_ANSWER);
            d.flags |= ShowingNoAnswer;
        }
        else
        {
            emit(out, Kind::DisplayOff);
        }
    }
    goOff(d, n, night, out);
}

void enterRunning(SessionData& d)
{
    d.state = SessionState::Running;
    d.inStateMs = 0;
    d.sincePingMs = 0;
    d.missedPings = 0;
}

// Eine offene Anfrage bleibt offen; SHUTDOWN geht, sobald die Leitung frei ist.
void enterShuttingDown(SessionData& d)
{
    d.state = SessionState::ShuttingDown;
    d.inStateMs = 0;
    d.sinceBusyMs = 0;
    d.flags = static_cast<uint8_t>((d.flags | NeedShutdown) & ~(NeedSession | PendingShutdown));
    d.buttonCount = 0;
}

// Pi zurueck aus EINSCHALTEN oder RADAR-DEBUG: gemerktes BT2 faehrt herunter (R9).
void piBack(SessionData& d, bool sendSession)
{
    if (isSet(d, PendingShutdown))
    {
        enterShuttingDown(d);
        return;
    }
    enterRunning(d);
    if (sendSession) d.flags |= NeedSession;
}

// Herunterfahren wie nach BT2; aus RADAR-DEBUG erst nach MODE|NORMAL (R9).
void shutDown(SessionData& d)
{
    if (d.state == SessionState::Running) enterShuttingDown(d);
    else if (d.state == SessionState::RadarDebug) d.flags |= PendingShutdown;
}

// SESSION abgelaufen oder nicht OK: herunterfahren wie nach BT2 (Spec 6.2).
void sessionFailed(SessionData& d, const std::string& why, Out& out)
{
    emit(out, Kind::Log, why);
    shutDown(d);
}

// Auftrag gescheitert. In der Nacht faehrt der ESP den Pi herunter (Spec 9),
// in einer Sitzung von Hand laeuft sie weiter.
void nightFailed(SessionData& d, NightData& n, NightResult why, const std::string& log, Out& out)
{
    emit(out, Kind::Log, log);
    n.status = NightStatus::Failed;
    n.result = why;
    if (d.reason == StartReason::Night) shutDown(d);
}

// Antwort QUOTE auf GET. Ein abgelehntes Zitat holt der ESP noch einmal, nach
// dem dritten gilt der Versuch als gescheitert (Z6). Erfolg zaehlt beim
// Empfang (R7); in der Nacht faehrt der ESP den Pi dann herunter (N2).
void onQuote(SessionData& d, NightData& n, const std::string& quote, Out& out)
{
    if (!QuoteCheck::acceptable(quote))
    {
        ++n.rejects;
        const std::string log = "Zitat abgelehnt (" + number(n.rejects) + "): " + quote;
        if (n.rejects >= NightJob::MAX_REJECTS) nightFailed(d, n, NightResult::Rejected, log, out);
        else emit(out, Kind::Log, log);
        return;
    }
    std::memset(n.quote, 0, sizeof n.quote);
    std::memcpy(n.quote, quote.data(), quote.size());
    std::memcpy(n.doneDate, n.date, sizeof n.doneDate);
    n.status = NightStatus::Got;
    n.result = NightResult::Ok;
    n.pendingWrite = 1;
    emit(out, Kind::QuoteReady, quote);
    if (d.reason == StartReason::Night) shutDown(d);
}

// Jede Antwort laesst eine zweite gleiche Anfrage ohne Wirkung (R8).
void onRequest(SessionData& d, const LinkCodec::Message& m, Out& out)
{
    const SessionState st = d.state;
    if (m.command == "READY")
    {
        emit(out, Kind::Reply, "OK");
        if (st == SessionState::Starting || st == SessionState::RadarDebug) piBack(d, true);
        else if (st == SessionState::Running) d.flags |= NeedSession;   // L3
        return;
    }
    if (m.command == "DONE")
    {
        emit(out, Kind::Reply, "OK");
        if (st == SessionState::Running || st == SessionState::RadarDebug) enterShuttingDown(d);
        return;
    }
    if (m.command == "MODE" && m.data == "RADAR")
    {
        if (st != SessionState::Running && st != SessionState::RadarDebug)
        {
            emit(out, Kind::Reply, "ERROR", "STATE");   // R12
            return;
        }
        emit(out, Kind::Reply, "OK");
        if (st == SessionState::Running)
        {
            d.state = SessionState::RadarDebug;
            d.inStateMs = 0;
        }
        return;
    }
    if (m.command == "MODE" && m.data == "NORMAL")
    {
        emit(out, Kind::Reply, "OK");
        if (st == SessionState::RadarDebug) piBack(d, false);
        return;
    }
    emit(out, Kind::Reply, "ERROR", "UNKNOWN");
}

void onResponse(SessionData& d, NightData& n, const LinkCodec::Message& m, Out& out)
{
    const Awaiting was = d.awaiting;
    d.awaiting = Awaiting::None;
    const bool ok = m.command == "OK";
    switch (was)
    {
    case Awaiting::None:
        emit(out, Kind::Log, "Antwort ohne Anfrage: " + m.command);
        break;
    case Awaiting::Ping:
        d.missedPings = 0;
        break;
    case Awaiting::Session:
        if (!ok) sessionFailed(d, "SESSION: " + m.command, out);
        break;
    case Awaiting::Shutdown:
        if (ok)
        {
            d.state = SessionState::Halting;
            d.inStateMs = 0;
            if (d.reason == StartReason::Hand) emit(out, Kind::Show, TEXT_HALTING);
        }
        else
        {
            d.sinceBusyMs = 0;   // nach BUSY_RETRY_MS noch einmal
        }
        break;
    case Awaiting::Button:
        if (!ok) emit(out, Kind::Log, "BUTTON: " + m.command);
        break;
    case Awaiting::Get:
        if (m.command == "QUOTE") onQuote(d, n, m.data, out);
        else nightFailed(d, n, NightResult::Error, "GET: " + m.command + (m.data.empty() ? "" : "|" + m.data), out);
        break;
    }
}

void onExpired(SessionData& d, NightData& n, const LinkCodec::Message& m, Out& out)
{
    const Awaiting was = d.awaiting;
    d.awaiting = Awaiting::None;
    switch (was)
    {
    case Awaiting::None:
        emit(out, Kind::Log, "Frist ohne Anfrage: " + m.command);
        break;
    case Awaiting::Ping:
        // Nur im Betrieb ein Aussetzer; in RADAR-DEBUG hoert der Pi auf 115 200 Baud.
        if (d.state != SessionState::Running)
        {
            emit(out, Kind::Log, "PING abgelaufen");
            break;
        }
        ++d.missedPings;
        if (d.missedPings >= PING_MISSES) hardOff(d, n, true, "PING ohne Antwort", NightResult::NoAnswer, out);
        else emit(out, Kind::Log, "PING-Aussetzer " + number(d.missedPings));
        break;
    case Awaiting::Session:
        sessionFailed(d, "SESSION abgelaufen", out);
        break;
    case Awaiting::Shutdown:
        hardOff(d, n, false, "SHUTDOWN ohne Antwort", NightResult::SessionEnded, out);
        break;
    case Awaiting::Button:
        emit(out, Kind::Log, "BUTTON abgelaufen");
        break;
    case Awaiting::Get:
        nightFailed(d, n, NightResult::NoAnswer, "GET abgelaufen", out);   // L2
        break;
    }
}

// Reihenfolge nach R2 und R8 (Teil 3b): SESSION, SHUTDOWN, BUTTON, GET, PING.
// Solange GET offen ist, geht kein PING (L2).
void sendNext(SessionData& d, const NightData& n, Out& out)
{
    const bool running = d.state == SessionState::Running;
    if (running && isSet(d, NeedSession))
    {
        d.flags &= static_cast<uint8_t>(~NeedSession);
        d.awaiting = Awaiting::Session;
        emit(out, Kind::Send, "SESSION", d.reason == StartReason::Hand ? "HAND" : "NACHT");
    }
    else if (d.state == SessionState::ShuttingDown && isSet(d, NeedShutdown))
    {
        d.flags &= static_cast<uint8_t>(~NeedShutdown);
        d.awaiting = Awaiting::Shutdown;
        emit(out, Kind::Send, "SHUTDOWN");
    }
    else if (running && d.buttonCount > 0)
    {
        const uint8_t button = d.buttons[0];
        for (uint8_t i = 1; i < d.buttonCount; ++i) d.buttons[i - 1] = d.buttons[i];
        d.buttons[--d.buttonCount] = 0;
        d.awaiting = Awaiting::Button;
        emit(out, Kind::Send, "BUTTON", number(button));
    }
    else if (running && n.status == NightStatus::Wanted)
    {
        d.awaiting = Awaiting::Get;
        emit(out, Kind::Send, "GET", "QUOTE|" + field(n.yesterday, sizeof n.yesterday));
    }
    else if (running && d.sincePingMs >= PING_INTERVAL_MS)
    {
        d.sincePingMs = 0;
        d.awaiting = Awaiting::Ping;
        emit(out, Kind::Send, "PING");
    }
}
}   // namespace

PiSession::PiSession(SessionData& data, NightData& night) : m_d(data), m_n(night) {}

void PiSession::reset(SessionData& data)
{
    data = SessionData();
}

// Ein Zustand ausserhalb der Liste schliefe nie ein, ein zu grosses
// buttonCount schriebe neben die Warteschlange.
bool PiSession::valid(const SessionData& data)
{
    return static_cast<uint8_t>(data.state) <= static_cast<uint8_t>(SessionState::Halting) &&
           static_cast<uint8_t>(data.reason) <= static_cast<uint8_t>(StartReason::Night) &&
           static_cast<uint8_t>(data.awaiting) <= static_cast<uint8_t>(Awaiting::Get) &&
           data.buttonCount <= sizeof(data.buttons);
}

bool PiSession::active() const
{
    return m_d.state != SessionState::Off || isSet(m_d, ShowingNoAnswer);
}

void PiSession::resume(Out& out)
{
    switch (m_d.awaiting)
    {
    case Awaiting::Session: m_d.flags |= NeedSession; break;
    case Awaiting::Shutdown: m_d.flags |= NeedShutdown; break;
    case Awaiting::Button: emit(out, Kind::Log, "BUTTON durch Reset abgebrochen"); break;
    case Awaiting::Get: break;   // Wanted bleibt: GET geht noch einmal, ohne Ablehnung
    default: break;   // ein abgebrochenes PING zaehlt nicht (R8)
    }
    m_d.awaiting = Awaiting::None;
}

void PiSession::startHand(Out& out)
{
    if (m_d.state != SessionState::Off) return;
    start(m_d, StartReason::Hand, out);   // beendet auch PI ANTWORTET NICHT
}

void PiSession::startNight(Out& out)
{
    if (m_d.state != SessionState::Off || isSet(m_d, ShowingNoAnswer)) return;
    start(m_d, StartReason::Night, out);
}

// Laeuft schon ein Auftrag oder ist das Zitat da, beginnt kein neuer.
bool PiSession::canRequestQuote() const
{
    if (m_d.state != SessionState::Starting && m_d.state != SessionState::Running) return false;
    return m_n.status != NightStatus::Wanted && m_n.status != NightStatus::Got;
}

bool PiSession::requestQuote()
{
    if (!canRequestQuote()) return false;
    m_n.status = NightStatus::Wanted;
    m_n.rejects = 0;
    m_n.result = NightResult::None;
    return true;
}

void PiSession::onButton(int button, Out& out)
{
    if (button < 1 || button > 6) return;
    if (m_d.reason == StartReason::Night)
    {
        // BT1, BT3-BT6 bleiben beim ESP (N2). BT2 macht eine Sitzung von Hand
        // daraus (N3): SESSION|HAND nach READY, oder sobald die Leitung frei ist.
        // RADAR-DEBUG kommt in der Nacht nicht vor; HERUNTERFAHREN, HALT-WARTEN: nichts.
        const SessionState st = m_d.state;
        if (button != 2 || (st != SessionState::Starting && st != SessionState::Running)) return;
        m_d.reason = StartReason::Hand;
        emit(out, Kind::Show, TEXT_STARTING);
        if (st == SessionState::Running) m_d.flags |= NeedSession;
        return;
    }
    switch (m_d.state)
    {
    case SessionState::Starting:
    case SessionState::RadarDebug:
        if (button == 2) m_d.flags |= PendingShutdown;
        break;
    case SessionState::Running:
        if (button == 2) enterShuttingDown(m_d);
        else if (m_d.buttonCount < sizeof(m_d.buttons)) m_d.buttons[m_d.buttonCount++] = static_cast<uint8_t>(button);
        else emit(out, Kind::Log, "Taste verworfen: " + number(static_cast<uint32_t>(button)));
        break;
    default:
        break;   // AUS macht die Application; HERUNTERFAHREN, HALT-WARTEN: nichts
    }
}

void PiSession::onLink(const LinkEvent& event, Out& out)
{
    if (event.kind == LinkEvent::Kind::None) return;
    if (m_d.state == SessionState::Off)
    {
        emit(out, Kind::Log, "ausserhalb der Sitzung: " + event.message.command);
        return;
    }
    switch (event.kind)
    {
    case LinkEvent::Kind::Request: onRequest(m_d, event.message, out); break;
    case LinkEvent::Kind::Response: onResponse(m_d, m_n, event.message, out); break;
    case LinkEvent::Kind::Expired: onExpired(m_d, m_n, event.message, out); break;
    default: break;
    }
}

void PiSession::onTick(unsigned long elapsedMs, bool linkBusy, Out& out)
{
    SessionData& d = m_d;
    const uint32_t dt = toMs(elapsedMs);
    if (d.state == SessionState::Off)
    {
        if (!isSet(d, ShowingNoAnswer)) return;
        addMs(d.inStateMs, dt);
        if (d.inStateMs >= NO_ANSWER_MS)
        {
            emit(out, Kind::DisplayOff);
            d.flags &= static_cast<uint8_t>(~ShowingNoAnswer);
        }
        return;
    }
    addMs(d.inStateMs, dt);
    addMs(d.sessionMs, dt);
    switch (d.state)
    {
    case SessionState::Starting:
        if (d.inStateMs >= BOOT_MS)
        {
            hardOff(d, m_n, true, "kein READY", NightResult::NoReady, out);
            return;
        }
        break;
    case SessionState::Running:
        addMs(d.sincePingMs, dt);
        break;
    case SessionState::RadarDebug:
        if (d.inStateMs >= RADAR_MAX_MS) enterShuttingDown(d);
        break;
    case SessionState::ShuttingDown:
        if (d.inStateMs >= BUSY_MAX_MS)
        {
            hardOff(d, m_n, false, "10 min ohne OK auf SHUTDOWN", NightResult::SessionEnded, out);
            return;
        }
        addMs(d.sinceBusyMs, dt);
        if (d.awaiting == Awaiting::None && !isSet(d, NeedShutdown) && d.sinceBusyMs >= BUSY_RETRY_MS)
            d.flags |= NeedShutdown;
        break;
    case SessionState::Halting:
        if (d.inStateMs >= HALT_MS)
        {
            emit(out, Kind::PowerOff);
            if (d.reason == StartReason::Hand) emit(out, Kind::DisplayOff);
            goOff(d, m_n, NightResult::SessionEnded, out);
            return;
        }
        break;
    default:
        break;
    }
    if (!linkBusy && d.awaiting == Awaiting::None) sendNext(d, m_n, out);
}
