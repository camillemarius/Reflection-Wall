#pragma once
// Verbindungsschicht ESP-Pi: Nummern, Bestaetigung, Wiederholung, Fristen, doppelte Nachrichten.
#include <cstdint>
#include <string>
#include "ISerialPort.h"
#include "LinkCodec.h"

struct LinkEvent
{
    enum class Kind { None, Request, Response, Expired };
    Kind kind = Kind::None;
    LinkCodec::Message message;   // Request: Anfrage des Pi; Response: Antwort; Expired: die eigene Anfrage
};

struct LinkState
{
    uint8_t txSeq = 0;
    uint8_t rxSeq = 0;
    bool rxValid = false;
};

class PiLink
{
public:
    static constexpr unsigned long REPEAT_MS = 250;
    explicit PiLink(ISerialPort& port);
    // false: schon eine Anfrage offen oder nicht kodierbar; verbraucht dann keine Nummer
    bool send(const std::string& command, const std::string& data, unsigned long nowMs);
    // liest, bis ein Ereignis da ist oder nichts mehr wartet; danach Frist und Wiederholung
    LinkEvent poll(unsigned long nowMs);
    // beantwortet die zuletzt gemeldete Anfrage des Pi; false, wenn keine offen ist
    bool reply(const std::string& command, const std::string& data = std::string());
    bool busy() const { return m_open; }
    unsigned long discarded() const { return m_discarded; }
    LinkCodec::Error lastError() const { return m_lastError; }
    LinkState state() const;              // txSeq = naechste Nummer
    void restore(const LinkState& s);

private:
    void writeLine(const std::string& line);
    bool handleLine(const std::string& line, LinkEvent& ev);

    ISerialPort& m_port;
    uint8_t m_txSeq = 0;
    uint8_t m_rxSeq = 0;
    bool m_rxValid = false;
    bool m_inProgress = false;       // Anfrage des Pi gemeldet, noch nicht beantwortet
    std::string m_lastReply;         // letzte Antwortzeile (ohne '\n'), leer wenn unbekannt

    bool m_open = false;
    LinkCodec::Message m_pending;
    std::string m_pendingLine;
    unsigned long m_start = 0;
    unsigned long m_lastSent = 0;

    std::string m_buf;
    bool m_overflow = false;
    unsigned long m_discarded = 0;
    LinkCodec::Error m_lastError = LinkCodec::Error::None;
};
