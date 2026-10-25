#pragma once
// Nachricht <-> Zeile der Verbindung ESP-Pi, ohne Arduino.
// Format: $NN:BEFEHL|DATEN*hh (ohne '\n').
#include <cstddef>
#include <cstdint>
#include <string>

namespace LinkCodec
{
constexpr std::size_t MAX_LINE = 256;   // Bytes ohne '\n'

enum class Error { None, NoStart, TooLong, BadChar, BadFormat, BadChecksum, BadCommand, BadEscape };
enum class Role { Unknown, EspRequest, PiRequest, Response };

struct Message
{
    uint8_t seq = 0;
    std::string command;
    std::string data;   // unmaskiert
};

Error encode(const Message& msg, std::string& line);   // line ohne '\n'; bei Fehler unveraendert
Error decode(const std::string& line, Message& msg);   // line ohne '\n'
Role roleOf(const std::string& command);
unsigned long deadlineMs(const std::string& command);  // GET 120000, SHUTDOWN 60000, sonst 3000
const char* errorName(Error e);
const char* roleName(Role r);
}   // namespace LinkCodec
