#include "WifiController.h"
#include "DebugLogger.h"

#define Serial DebugSerial

#include <ESP8266WiFi.h>
#include <WiFiManager.h>
#include <time.h>

bool WifiController::begin()
{
    WiFiManager wifiManager;

    wifiManager.setHostname("reflectionwall");

    Serial.println("Starting WiFi...");

    if (!wifiManager.autoConnect("ReflectionWall"))
    {
        Serial.println("WiFi connection failed");
        return false;
    }

    Serial.println("WiFi connected");

    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());

    setenv("TZ", "CET-1CEST,M3.5.0,M10.5.0/3", 1);
    tzset();
    configTime(0, 0, "pool.ntp.org", "time.nist.gov");

    return true;
}

bool WifiController::isConnected() const
{
    return WiFi.status() == WL_CONNECTED;
}