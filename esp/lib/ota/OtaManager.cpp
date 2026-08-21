#include "OtaManager.h"
#include "DebugLogger.h"

#define Serial DebugSerial

void OtaManager::begin(const char* hostname)
{
    ArduinoOTA.setHostname(hostname);

    ArduinoOTA.onStart([]()
    {
        Serial.println();
        Serial.println("=== OTA START ===");
    });

    ArduinoOTA.onEnd([]()
    {
        Serial.println();
        Serial.println("=== OTA END ===");
    });

    ArduinoOTA.onProgress([](unsigned int progress, unsigned int total)
    {
        unsigned int percent = (progress * 100) / total;

        Serial.printf(
            "OTA: %u%%\r",
            percent
        );
    });

    ArduinoOTA.onError([](ota_error_t error)
    {
        Serial.printf(
            "\nOTA ERROR[%u]: ",
            error
        );

        switch (error)
        {
            case OTA_AUTH_ERROR:
                Serial.println("Auth Failed");
                break;

            case OTA_BEGIN_ERROR:
                Serial.println("Begin Failed");
                break;

            case OTA_CONNECT_ERROR:
                Serial.println("Connect Failed");
                break;

            case OTA_RECEIVE_ERROR:
                Serial.println("Receive Failed");
                break;

            case OTA_END_ERROR:
                Serial.println("End Failed");
                break;

            default:
                Serial.println("Unknown Error");
                break;
        }
    });

    ArduinoOTA.begin();

    Serial.print("OTA ready: ");
    Serial.println(hostname);
}

void OtaManager::handle()
{
    ArduinoOTA.handle();
}