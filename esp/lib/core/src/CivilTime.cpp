#include "CivilTime.h"

#include <cstdio>

namespace
{
    // Tage seit 1970-01-01 (proleptisch gregorianisch)
    int64_t daysFromCivil(int y, int m, int d)
    {
        y -= (m <= 2) ? 1 : 0;
        const int64_t era = (y >= 0 ? y : y - 399) / 400;
        const int64_t yoe = y - era * 400;
        const int64_t doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
        const int64_t doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
        return era * 146097 + doe - 719468;
    }

    void civilFromDays(int64_t z, int& y, int& m, int& d)
    {
        z += 719468;
        const int64_t era = (z >= 0 ? z : z - 146096) / 146097;
        const int64_t doe = z - era * 146097;
        const int64_t yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
        const int64_t doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
        const int64_t mp = (5 * doy + 2) / 153;
        d = static_cast<int>(doy - (153 * mp + 2) / 5 + 1);
        m = static_cast<int>(mp < 10 ? mp + 3 : mp - 9);
        y = static_cast<int>(yoe + era * 400 + (m <= 2 ? 1 : 0));
    }

    // Letzter Sonntag des Monats, als Tag seit 1970
    int64_t lastSunday(int year, int month)
    {
        const int nextYear = (month == 12) ? year + 1 : year;
        const int nextMonth = (month == 12) ? 1 : month + 1;
        const int64_t last = daysFromCivil(nextYear, nextMonth, 1) - 1;
        const int weekday = static_cast<int>(((last + 4) % 7 + 7) % 7); // 0 = Sonntag
        return last - weekday;
    }

    int64_t floorDiv(int64_t a, int64_t b)
    {
        return a / b - ((a % b != 0 && (a < 0)) ? 1 : 0);
    }
}

namespace CivilTime
{
    bool isSummer(uint32_t utc)
    {
        int y, m, d;
        civilFromDays(floorDiv(utc, 86400), y, m, d);
        const int64_t start = lastSunday(y, 3) * 86400 + 3600;
        const int64_t end = lastSunday(y, 10) * 86400 + 3600;
        return utc >= start && utc < end;
    }

    Local toZurich(uint32_t utc)
    {
        Local t;
        t.summer = isSummer(utc);
        const int64_t local = static_cast<int64_t>(utc) + (t.summer ? 7200 : 3600);
        const int64_t days = floorDiv(local, 86400);
        const int sec = static_cast<int>(local - days * 86400);
        civilFromDays(days, t.year, t.month, t.day);
        t.hour = sec / 3600;
        t.minute = (sec % 3600) / 60;
        t.second = sec % 60;
        return t;
    }

    uint32_t atLocalHour(int year, int month, int day, int hour)
    {
        const int64_t local = daysFromCivil(year, month, day) * 86400 + hour * 3600;
        // Sommerzeit zuerst: bei doppelter Stunde gilt das erste Mal
        const uint32_t summer = static_cast<uint32_t>(local - 7200);
        if (isSummer(summer))
        {
            return summer;
        }
        // Sonst Winterzeit; in der Luecke (Fruehling) ist das der Wechselzeitpunkt
        return static_cast<uint32_t>(local - 3600);
    }

    uint32_t nextLocalHour(uint32_t utc, int hour)
    {
        const Local now = toZurich(utc);
        const int64_t today = daysFromCivil(now.year, now.month, now.day);
        for (int i = 0; i < 3; ++i)
        {
            int y, m, d;
            civilFromDays(today + i, y, m, d);
            const uint32_t candidate = atLocalHour(y, m, d, hour);
            if (candidate > utc)
            {
                return candidate;
            }
        }
        return utc; // unerreichbar: spaetestens der naechste Tag liegt danach
    }

    std::string date(const Local& t)
    {
        char buf[16];
        std::snprintf(buf, sizeof(buf), "%04d-%02d-%02d", t.year, t.month, t.day);
        return buf;
    }
}
