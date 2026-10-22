#pragma once
// Liest tests/protocol_vectors.json (nur fuer Tests, header-only).
// Nur das feste Format der Datei: ein flaches Objekt je Zeile.
#include <cstdlib>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

struct Vector
{
    std::map<std::string, std::string> text;
    std::map<std::string, long> number;

    std::string str(const char* key) const
    {
        auto it = text.find(key);
        return it == text.end() ? std::string() : it->second;
    }
    long num(const char* key) const
    {
        auto it = number.find(key);
        return it == number.end() ? -1 : it->second;
    }
    bool has(const char* key) const { return text.count(key) > 0 || number.count(key) > 0; }
};

constexpr char PROTOCOL_VECTORS[] = "../tests/protocol_vectors.json";   // pio test laeuft in esp/

namespace vectorfile_detail
{
inline int hexVal(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

inline void skipSpace(const std::string& s, std::size_t& i)
{
    while (i < s.size() && (s[i] == ' ' || s[i] == '\t')) ++i;
}

// liest "..." ab s[i] == '"'; i steht danach hinter dem schliessenden '"'
inline bool readString(const std::string& s, std::size_t& i, std::string& out, std::string& why)
{
    out.clear();
    ++i;
    while (i < s.size())
    {
        char c = s[i++];
        if (c == '"') return true;
        if (c != '\\')
        {
            out += c;
            continue;
        }
        if (i >= s.size()) break;
        char e = s[i++];
        switch (e)
        {
        case '"': out += '"'; break;
        case '\\': out += '\\'; break;
        case '/': out += '/'; break;
        case 'n': out += '\n'; break;
        case 'r': out += '\r'; break;
        case 't': out += '\t'; break;
        case 'u':
        {
            if (i + 4 > s.size()) { why = "kurzes \\u"; return false; }
            int v = 0;
            for (int k = 0; k < 4; ++k)
            {
                int h = hexVal(s[i + k]);
                if (h < 0) { why = "\\u ohne Hex"; return false; }
                v = v * 16 + h;
            }
            i += 4;
            if (v > 0xFF) { why = "\\u ueber 00FF"; return false; }
            out += static_cast<char>(v);
            break;
        }
        default: why = "unbekannter Escape"; return false;
        }
    }
    why = "Zeichenkette nicht beendet";
    return false;
}

inline bool parseObject(const std::string& s, std::size_t i, Vector& v, std::string& why)
{
    ++i;   // '{'
    while (true)
    {
        skipSpace(s, i);
        if (i >= s.size() || s[i] != '"') { why = "Schluessel erwartet"; return false; }
        std::string key, val;
        if (!readString(s, i, key, why)) return false;
        skipSpace(s, i);
        if (i >= s.size() || s[i] != ':') { why = "':' erwartet"; return false; }
        ++i;
        skipSpace(s, i);
        if (i >= s.size()) { why = "Wert erwartet"; return false; }
        if (s[i] == '"')
        {
            if (!readString(s, i, val, why)) return false;
            v.text[key] = val;
        }
        else
        {
            std::size_t st = i;
            if (s[i] == '-') ++i;
            std::size_t digits = i;
            while (i < s.size() && s[i] >= '0' && s[i] <= '9') ++i;
            if (i == digits) { why = "Zahl erwartet"; return false; }
            v.number[key] = std::strtol(s.substr(st, i - st).c_str(), nullptr, 10);
        }
        skipSpace(s, i);
        if (i >= s.size()) { why = "'}' fehlt"; return false; }
        if (s[i] == ',') { ++i; continue; }
        if (s[i] == '}')
        {
            ++i;
            skipSpace(s, i);
            if (i < s.size() && s[i] == ',') ++i;
            skipSpace(s, i);
            if (i != s.size()) { why = "Rest nach '}'"; return false; }
            return true;
        }
        why = "',' oder '}' erwartet";
        return false;
    }
}
}   // namespace vectorfile_detail

inline bool loadVectors(const char* path, std::vector<Vector>& out, std::string& error)
{
    std::ifstream f(path, std::ios::binary);
    if (!f)
    {
        error = path;
        return false;
    }
    std::stringstream ss;
    ss << f.rdbuf();
    std::string all = ss.str();

    std::size_t pos = 0;
    int lineNo = 0;
    while (pos <= all.size())
    {
        std::size_t nl = all.find('\n', pos);
        std::string line = all.substr(pos, nl == std::string::npos ? std::string::npos : nl - pos);
        pos = nl == std::string::npos ? all.size() + 1 : nl + 1;
        ++lineNo;
        if (!line.empty() && line.back() == '\r') line.pop_back();
        std::size_t i = 0;
        vectorfile_detail::skipSpace(line, i);
        if (line.compare(i, 2, "{\"") != 0) continue;
        Vector v;
        std::string why;
        if (!vectorfile_detail::parseObject(line, i, v, why))
        {
            error = "Zeile " + std::to_string(lineNo) + ": " + why;
            return false;
        }
        out.push_back(v);
    }
    return true;
}
