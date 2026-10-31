#include "TimeSync.h"
#include "DebugLogger.h"

#define Serial DebugSerial

#include <ESP8266WiFi.h>
#include <WiFiManager.h>
#include <time.h>

namespace
{
    // 2024-01-01 00:00:00 UTC: alles davor ist keine gueltige NTP-Zeit
    constexpr time_t MIN_VALID_UTC = 1704067200;

    void radioOff()
    {
        WiFi.disconnect(true);
        WiFi.mode(WIFI_OFF);
        WiFi.forceSleepBegin();
    }
}

bool TimeSync::hasCredentials()
{
    // Nach dem Start ist WiFi.SSID() vor begin() nicht verlaesslich;
    // darum die gespeicherte Konfiguration des SDK lesen.
    struct station_config conf;
    memset(&conf, 0, sizeof(conf));

    if (!wifi_station_get_config_default(&conf))
        return false;

    return conf.ssid[0] != 0;
}

bool TimeSync::sync(unsigned long timeoutMs, uint32_t& utc)
{
    const unsigned long start = millis();
    bool ok = false;

    WiFi.forceSleepWake();
    delay(1);
    WiFi.persistent(false);
    WiFi.mode(WIFI_STA);
    WiFi.begin();

    Serial.println("[TIME] WLAN verbinden");

    while (WiFi.status() != WL_CONNECTED && millis() - start < timeoutMs)
        delay(50);

    if (WiFi.status() == WL_CONNECTED)
    {
        Serial.println("[TIME] verbunden, NTP");

        configTime(0, 0, "pool.ntp.org", "time.nist.gov");

        while (time(nullptr) < MIN_VALID_UTC && millis() - start < timeoutMs)
            delay(50);

        const time_t now = time(nullptr);

        if (now >= MIN_VALID_UTC)
        {
            utc = static_cast<uint32_t>(now);
            ok = true;
        }
    }

    Serial.printf("[TIME] %s nach %lu ms\n", ok ? "Zeit geholt" : "ohne Zeit", millis() - start);

    radioOff();

    return ok;
}

bool TimeSync::portal(unsigned long timeoutS)
{
    WiFi.forceSleepWake();
    delay(1);

    // Nur das Portal darf die Zugangsdaten im Flash ablegen.
    WiFi.persistent(true);

    bool ok;
    {
        WiFiManager wifiManager;

        wifiManager.setHostname("reflectionwall");
        wifiManager.setConfigPortalTimeout(timeoutS);
        wifiManager.setConnectTimeout(15);

        Serial.println("[TIME] Portal ReflectionWall");

        ok = wifiManager.autoConnect("ReflectionWall");
    }

    WiFi.persistent(false);

    Serial.println(ok ? "[TIME] Portal: verbunden" : "[TIME] Portal: ohne Verbindung");

    radioOff();

    return ok;
}
