#pragma once

#include <Arduino.h>
#include <Wire.h>

class HT16K33
{
public:

    static constexpr uint8_t CHARS_PER_MODULE = 8;
    static constexpr uint8_t BUFFER_SIZE = CHARS_PER_MODULE * 2;

    // Helligkeit 0..15. Die Anzeigen laufen bewusst nie voll
    // hell: der LED-Strom der ganzen Kette stoert sonst den
    // I2C-Bus. setBrightness() begrenzt auf MAX_BRIGHTNESS.
    static constexpr uint8_t DEFAULT_BRIGHTNESS = 4;
    static constexpr uint8_t MAX_BRIGHTNESS = 7;

    HT16K33(uint8_t address);

    void begin();
    void clear();

    void setText(const String& text);

    void setBrightness(uint8_t level);

    bool testConnection();

    uint8_t testConnectionCode();

    uint8_t getAddress() const;

    void testAllSegments();

    // Ergebnis der Schreibzugriffe seit resetWriteStats():
    // letzter Fehlercode von endTransmission() (0 = ok) und
    // Anzahl noetiger Wiederholungen.
    uint8_t lastWriteError() const;
    uint8_t writeRetries() const;
    void resetWriteStats();

private:

    // Ein gestoerter Bus bricht den 17-Byte-Zugriff mit NACK ab,
    // uebrig bleiben dann nur die ersten Zeichen.
    static constexpr uint8_t WRITE_ATTEMPTS = 3;

    uint8_t _lastError = 0;
    uint8_t _retries = 0;

    uint8_t _address;

    uint8_t _buffer[BUFFER_SIZE];

    void init();
    void write();

    void clearBuffer();

    void setChar(uint8_t position, char c);
};