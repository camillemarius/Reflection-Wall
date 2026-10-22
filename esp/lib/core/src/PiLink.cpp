#include "PiLink.h"

using namespace LinkCodec;

PiLink::PiLink(ISerialPort& port) : m_port(port) {}

void PiLink::writeLine(const std::string& line)
{
    m_port.write("\n" + line + "\n");
}

bool PiLink::send(const std::string& command, const std::string& data, unsigned long nowMs)
{
    if (m_open) return false;
    Message m;
    m.seq = m_txSeq;
    m.command = command;
    m.data = data;
    std::string line;
    if (encode(m, line) != Error::None) return false;
    ++m_txSeq;
    m_pending = m;
    m_pendingLine = line;
    m_open = true;
    m_start = nowMs;
    m_lastSent = nowMs;
    writeLine(line);
    return true;
}

bool PiLink::reply(const std::string& command, const std::string& data)
{
    if (!m_inProgress) return false;
    Message m;
    m.seq = m_rxSeq;
    m.command = command;
    m.data = data;
    std::string line;
    if (encode(m, line) != Error::None) return false;
    m_lastReply = line;
    m_inProgress = false;
    writeLine(line);
    return true;
}

bool PiLink::handleLine(const std::string& line, LinkEvent& ev)
{
    Message m;
    Error e = decode(line, m);
    if (e != Error::None)
    {
        ++m_discarded;
        m_lastError = e;
        return false;
    }
    if (roleOf(m.command) == Role::Response)
    {
        if (!m_open || m.seq != m_pending.seq) return false;
        m_open = false;
        ev.kind = LinkEvent::Kind::Response;
        ev.message = m;
        return true;
    }
    if (m_rxValid && m.seq == m_rxSeq)
    {
        if (!m_inProgress && !m_lastReply.empty()) writeLine(m_lastReply);
        return false;
    }
    m_rxSeq = m.seq;
    m_rxValid = true;
    m_lastReply.clear();
    if (roleOf(m.command) != Role::PiRequest)
    {
        Message r;
        r.seq = m.seq;
        r.command = "ERROR";
        r.data = "UNKNOWN";
        encode(r, m_lastReply);
        m_inProgress = false;
        writeLine(m_lastReply);
        return false;
    }
    m_inProgress = true;
    ev.kind = LinkEvent::Kind::Request;
    ev.message = m;
    return true;
}

LinkEvent PiLink::poll(unsigned long nowMs)
{
    LinkEvent ev;
    for (;;)
    {
        int c = m_port.read();
        if (c < 0) break;
        if (c != '\n')
        {
            if (m_overflow) continue;
            if (m_buf.size() >= MAX_LINE + 1) { m_overflow = true; m_buf.clear(); continue; }
            m_buf += static_cast<char>(c);
            continue;
        }
        if (m_overflow)
        {
            m_overflow = false;
            ++m_discarded;
            m_lastError = Error::TooLong;
            continue;
        }
        std::string line;
        line.swap(m_buf);
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty()) continue;
        if (handleLine(line, ev)) return ev;
    }
    if (m_open)
    {
        if (nowMs - m_start >= deadlineMs(m_pending.command))
        {
            m_open = false;
            ev.kind = LinkEvent::Kind::Expired;
            ev.message = m_pending;
            return ev;
        }
        if (nowMs - m_lastSent >= REPEAT_MS)
        {
            m_lastSent = nowMs;
            writeLine(m_pendingLine);
        }
    }
    return ev;
}

LinkState PiLink::state() const
{
    LinkState s;
    s.txSeq = m_txSeq;
    s.rxSeq = m_rxSeq;
    s.rxValid = m_rxValid;
    return s;
}

void PiLink::restore(const LinkState& s)
{
    m_txSeq = s.txSeq;
    m_rxSeq = s.rxSeq;
    m_rxValid = s.rxValid;
    m_inProgress = false;
    m_lastReply.clear();
}
