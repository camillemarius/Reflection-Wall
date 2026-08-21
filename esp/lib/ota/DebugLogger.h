#pragma once

#include <Arduino.h>
#include <ESP8266WiFi.h>

class DebugLogger : public Print
{
public:
    explicit DebugLogger(HardwareSerial& serial);

    void begin(unsigned long baudRate);
    void beginNetwork();
    void handle();

    size_t write(uint8_t value) override;
    size_t write(const uint8_t* buffer, size_t size) override;
    using Print::write;

    size_t printf(const char* format, ...);

private:
    static constexpr size_t HISTORY_SIZE = 16384;

    HardwareSerial& _serial;
    WiFiServer _server;
    WiFiClient _client;
    uint8_t _history[HISTORY_SIZE];
    size_t _historyStart;
    size_t _historyLength;

    void storeHistory(const uint8_t* buffer, size_t size);
    void sendHistory();
};

extern DebugLogger DebugSerial;
