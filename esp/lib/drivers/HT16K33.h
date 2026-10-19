#pragma once

#include <Arduino.h>
#include <Wire.h>

class HT16K33
{
public:

    static constexpr uint8_t CHARS_PER_MODULE = 8;
    static constexpr uint8_t BUFFER_SIZE = CHARS_PER_MODULE * 2;

    // Helligkeit 0..15 (Tastverhaeltnis (n+1)/16). Volle
    // Helligkeit setzt den PCA9517A voraus: ohne ihn stoerte der
    // LED-Strom der ganzen Kette den I2C-Bus, die Anzeigen liefen
    // deshalb auf hoechstens 7. Der Buffer-Test laeuft mit
    // DEFAULT_BRIGHTNESS und prueft den Bus damit unter voller Last.
    static constexpr uint8_t DEFAULT_BRIGHTNESS = 15;
    static constexpr uint8_t MAX_BRIGHTNESS = 15;

    HT16K33(uint8_t address);

    void begin();
    void clear();

    void setText(const String& text);

    void setBrightness(uint8_t level);

    // Schaltet die Anzeige ab bzw. an. Der Inhalt bleibt im Chip
    // erhalten, die LEDs sind nur dunkel.
    void setDisplayOn(bool on);

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