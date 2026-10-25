#include "LinkCodec.h"

namespace LinkCodec
{
namespace
{
bool printable(char c)
{
    uint8_t b = static_cast<uint8_t>(c);
    return b >= 0x20 && b <= 0x7E;
}

bool validCommand(const std::string& cmd)
{
    if (cmd.empty()) return false;
    for (char c : cmd)
    {
        if (c < 'A' || c > 'Z') return false;
    }
    return true;
}

int hexVal(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

void appendHex(std::string& s, uint8_t v)
{
    static const char DIGITS[] = "0123456789ABCDEF";
    s += DIGITS[v >> 4];
    s += DIGITS[v & 0x0F];
}
}   // namespace

Error encode(const Message& msg, std::string& line)
{
    if (!validCommand(msg.command)) return Error::BadCommand;

    std::string escaped;
    for (char c : msg.data)
    {
        if (c == '\\') escaped += "\\\\";
        else if (c == '\n') escaped += "\\n";
        else if (c == '\r') escaped += "\\r";
        else if (printable(c)) escaped += c;
        else return Error::BadChar;
    }

    std::string body;
    appendHex(body, msg.seq);
    body += ':';
    body += msg.command;
    if (!escaped.empty())
    {
        body += '|';
        body += escaped;
    }

    uint8_t sum = 0;
    for (char c : body) sum ^= static_cast<uint8_t>(c);

    std::string out = "$" + body + "*";
    appendHex(out, sum);
    if (out.size() > MAX_LINE) return Error::TooLong;
    line = out;
    return Error::None;
}

Error decode(const std::string& line, Message& msg)
{
    if (line.size() > MAX_LINE) return Error::TooLong;
    if (line.empty() || line[0] != '$') return Error::NoStart;
    for (char c : line)
    {
        if (!printable(c)) return Error::BadChar;
    }

    std::size_t star = line.rfind('*');
    if (star == std::string::npos || star + 3 != line.size()) return Error::BadFormat;
    int h1 = hexVal(line[star + 1]);
    int h2 = hexVal(line[star + 2]);
    if (h1 < 0 || h2 < 0) return Error::BadFormat;

    uint8_t sum = 0;
    for (std::size_t i = 1; i < star; ++i) sum ^= static_cast<uint8_t>(line[i]);
    if (sum != static_cast<uint8_t>(h1 * 16 + h2)) return Error::BadChecksum;

    // body = line[1 .. star)
    if (star < 4) return Error::BadFormat;   // NN ':' mindestens
    int n1 = hexVal(line[1]);
    int n2 = hexVal(line[2]);
    if (n1 < 0 || n2 < 0 || line[3] != ':') return Error::BadFormat;

    std::size_t pipe = line.find('|', 4);
    if (pipe == std::string::npos || pipe > star) pipe = star;
    std::string command = line.substr(4, pipe - 4);
    if (!validCommand(command)) return Error::BadCommand;

    std::string data;
    if (pipe < star)
    {
        for (std::size_t i = pipe + 1; i < star; ++i)
        {
            char c = line[i];
            if (c != '\\')
            {
                data += c;
                continue;
            }
            if (i + 1 >= star) return Error::BadEscape;
            char e = line[++i];
            if (e == '\\') data += '\\';
            else if (e == 'n') data += '\n';
            else if (e == 'r') data += '\r';
            else return Error::BadEscape;
        }
    }

    msg.seq = static_cast<uint8_t>(n1 * 16 + n2);
    msg.command = command;
    msg.data = data;
    return Error::None;
}

Role roleOf(const std::string& command)
{
    if (command == "PING" || command == "GET" || command == "BUTTON" || command == "SHUTDOWN" || command == "SESSION")
        return Role::EspRequest;
    if (command == "READY" || command == "DONE" || command == "MODE")
        return Role::PiRequest;
    if (command == "PONG" || command == "QUOTE" || command == "OK" || command == "BUSY" || command == "ERROR")
        return Role::Response;
    return Role::Unknown;
}

unsigned long deadlineMs(const std::string& command)
{
    if (command == "GET") return 120000UL;
    if (command == "SHUTDOWN") return 60000UL;
    return 3000UL;
}

const char* errorName(Error e)
{
    switch (e)
    {
    case Error::None: return "NONE";
    case Error::NoStart: return "NO_START";
    case Error::TooLong: return "TOO_LONG";
    case Error::BadChar: return "BAD_CHAR";
    case Error::BadFormat: return "BAD_FORMAT";
    case Error::BadChecksum: return "BAD_CHECKSUM";
    case Error::BadCommand: return "BAD_COMMAND";
    case Error::BadEscape: return "BAD_ESCAPE";
    }
    return "NONE";
}

const char* roleName(Role r)
{
    switch (r)
    {
    case Role::Unknown: return "unknown";
    case Role::EspRequest: return "esp_request";
    case Role::PiRequest: return "pi_request";
    case Role::Response: return "response";
    }
    return "unknown";
}
}   // namespace LinkCodec
