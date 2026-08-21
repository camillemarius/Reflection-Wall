#pragma once

#include <Arduino.h>
#include <ArduinoOTA.h>

class OtaManager
{
public:
    static void begin(const char* hostname = "esp8266");
    static void handle();
};