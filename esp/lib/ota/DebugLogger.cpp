#include "DebugLogger.h"

#include <cstdarg>
#include <cstdio>
#include <ctime>

DebugLogger DebugSerial(Serial);

DebugLogger::DebugLogger(HardwareSerial& serial)
    : _serial(serial),
    _server(23),
    _historyStart(0),
    _historyLength(0)
{
}

void DebugLogger::begin(unsigned long baudRate)
{
    _serial.begin(baudRate);
}

void DebugLogger::beginNetwork()
{
    _server.begin();
    _server.setNoDelay(true);
}

void DebugLogger::handle()
{
    if (!_client || !_client.connected())
    {
        WiFiClient client = _server.accept();

        if (client)
        {
            _client = client;
            sendHistory();
            _client.println();

            time_t currentTime = time(nullptr);
            tm localTime;
            char timestamp[24];

            if (currentTime > 1577836800 && localtime_r(&currentTime, &localTime) != nullptr)
            {
                strftime(timestamp, sizeof(timestamp), "%Y-%m-%d %H:%M:%S", &localTime);
                _client.print("=== LIVE STREAM START: ");
                _client.print(timestamp);
                _client.println(" ===");
            }
            else
            {
                _client.println("=== LIVE STREAM START: Uhrzeit noch nicht synchronisiert ===");
            }
        }
    }
}

size_t DebugLogger::write(uint8_t value)
{
    return write(&value, 1);
}

size_t DebugLogger::write(const uint8_t* buffer, size_t size)
{
    _serial.write(buffer, size);
    storeHistory(buffer, size);

    if (_client && _client.connected())
        _client.write(buffer, size);

    return size;
}

void DebugLogger::storeHistory(const uint8_t* buffer, size_t size)
{
    for (size_t i = 0; i < size; i++)
    {
        if (_historyLength < HISTORY_SIZE)
        {
            size_t index = (_historyStart + _historyLength) % HISTORY_SIZE;
            _history[index] = buffer[i];
            _historyLength++;
        }
        else
        {
            _history[_historyStart] = buffer[i];
            _historyStart = (_historyStart + 1) % HISTORY_SIZE;
        }
    }
}

void DebugLogger::sendHistory()
{
    for (size_t i = 0; i < _historyLength; i++)
    {
        size_t index = (_historyStart + i) % HISTORY_SIZE;
        _client.write(_history[index]);
    }
}

size_t DebugLogger::printf(const char* format, ...)
{
    char buffer[192];
    va_list arguments;

    va_start(arguments, format);
    int length = vsnprintf(buffer, sizeof(buffer), format, arguments);
    va_end(arguments);

    if (length <= 0)
        return 0;

    size_t outputLength = static_cast<size_t>(length);
    if (outputLength >= sizeof(buffer))
        outputLength = sizeof(buffer) - 1;

    return write(reinterpret_cast<const uint8_t*>(buffer), outputLength);
}
