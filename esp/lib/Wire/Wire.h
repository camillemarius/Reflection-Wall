#pragma once

#include <Arduino.h>
#include <Stream.h>

// ---------------------------------------------------------
// Projektlokaler Ersatz fuer die Wire-Bibliothek des Cores
// ---------------------------------------------------------
// Die Software-I2C des ESP8266-Cores (core_esp8266_si2c.cpp)
// veraendert SDA unmittelbar nach "SCL low" - ohne Hold-Zeit.
// Auf diesem Bus faellt SCL an den Slaves aber spaeter als am
// ESP (BSS138-Pegelwandler, lange Kette, SCL ueber die
// LTC4316 durchgeschaltet). Kippt SDA, waehrend ein Slave SCL
// noch als high sieht, erkennt er ein falsches START/STOP und
// verwirft die Adresse -> NACK.
//
// Diese Implementierung wartet nach jedem "SCL low"
// I2C_SDA_HOLD_US, bevor SDA gesetzt oder freigegeben wird.
// Die Schnittstelle entspricht dem Teil von TwoWire, den das
// Projekt nutzt; die uebrigen Dateien bleiben unveraendert.
//
// Liegt in lib/Wire und hat damit Vorrang vor der
// gleichnamigen Framework-Bibliothek.

#ifndef BUFFER_LENGTH
#define BUFFER_LENGTH 32
#endif

// Wartezeit zwischen "SCL low" und der naechsten Aenderung an
// SDA. Startwert fuer die Fehlersuche; wird auf eine halbe
// Taktperiode minus 1 us begrenzt.
constexpr uint32_t I2C_SDA_HOLD_US = 10;

// Maximale Wartezeit, bis ein freigegebenes SCL tatsaechlich
// high ist (Clock Stretching bzw. haengender Bus).
constexpr uint32_t I2C_CLOCK_STRETCH_LIMIT_US = 20000;

class TwoWire : public Stream
{
public:
    void begin(int sda, int scl);
    void begin();

    void setClock(uint32_t frequency);
    void setClockStretchLimit(uint32_t limitUs);

    // Hold-Zeit zur Laufzeit aendern (z.B. fuer Versuchsreihen)
    void setSdaHold(uint32_t holdUs);

    // true: ein NACK auf ein Datenbyte bricht die Uebertragung
    // nicht ab, die restlichen Bytes werden trotzdem gesendet.
    // endTransmission() meldet dann dennoch Code 3.
    // Hintergrund: hinter den LTC4316 geht bei manchen Modulen
    // das ACK nach Bytes mit Bit 0 = 1 verloren, obwohl die
    // Daten ankommen.
    void setIgnoreDataNack(bool ignore) { _ignoreDataNack = ignore; }

    // Diagnose: tastet SDA waehrend des ACK-Takts nach jedem
    // Datenbyte ab (~1 Sample pro us). Nach endTransmission()
    // enthalten ackTraceLow()/ackTraceHigh() die Samples der
    // Low- bzw. High-Phase von SCL des letzten Datenbyte-ACKs
    // (Bit n = Sample n war HIGH).
    void setAckTrace(bool on) { _ackTrace = on; }
    uint64_t ackTraceLow() const { return _traceLow; }
    uint64_t ackTraceHigh() const { return _traceHigh; }
    uint8_t ackTraceLowCount() const { return _traceLowCount; }
    uint8_t ackTraceHighCount() const { return _traceHighCount; }

    // Dauer der 64 schnellen Samples in der Low-Phase (CPU-Takte)
    uint32_t ackTraceFastCycles() const { return _traceFastCycles; }

    // Diagnose: Zeit vom START bis zur fallenden SCL-Flanke vor dem
    // letzten ACK der letzten Uebertragung, in us
    uint32_t lastAckFallAfterStartUs() const { return _tAckFallUs - _tStartUs; }

    void beginTransmission(uint8_t address);
    void beginTransmission(int address) { beginTransmission((uint8_t)address); }

    // 0 = ok, 1 = Daten zu lang, 2 = NACK auf Adresse,
    // 3 = NACK auf Daten, 4 = Bus belegt / SCL-Timeout
    uint8_t endTransmission(uint8_t sendStop);
    uint8_t endTransmission() { return endTransmission(true); }

    uint8_t requestFrom(uint8_t address, uint8_t quantity, uint8_t sendStop);
    uint8_t requestFrom(uint8_t address, uint8_t quantity) { return requestFrom(address, quantity, (uint8_t)true); }
    uint8_t requestFrom(int address, int quantity) { return requestFrom((uint8_t)address, (uint8_t)quantity, (uint8_t)true); }
    uint8_t requestFrom(int address, int quantity, int sendStop) { return requestFrom((uint8_t)address, (uint8_t)quantity, (uint8_t)sendStop); }

    size_t write(uint8_t data) override;
    size_t write(const uint8_t* data, size_t length) override;

    inline size_t write(unsigned long n) { return write((uint8_t)n); }
    inline size_t write(long n)          { return write((uint8_t)n); }
    inline size_t write(unsigned int n)  { return write((uint8_t)n); }
    inline size_t write(int n)           { return write((uint8_t)n); }
    using Print::write;

    int available() override;
    int read() override;
    int peek() override;
    void flush();

private:
    int _sda = SDA;
    int _scl = SCL;

    uint32_t _halfPeriodUs = 5;
    uint32_t _holdUs = I2C_SDA_HOLD_US;
    uint32_t _stretchLimitUs = I2C_CLOCK_STRETCH_LIMIT_US;

    // true nach endTransmission(false) / requestFrom(..., false):
    // der naechste Start ist ein Repeated Start
    bool _busHeld = false;

    bool _ignoreDataNack = false;

    bool _ackTrace = false;
    uint64_t _traceLow = 0;
    uint64_t _traceHigh = 0;
    uint8_t _traceLowCount = 0;
    uint8_t _traceHighCount = 0;
    uint32_t _traceFastCycles = 0;
    uint32_t _tStartUs = 0;
    uint32_t _tAckFallUs = 0;

    uint8_t _txAddress = 0;
    uint8_t _txBuffer[BUFFER_LENGTH];
    uint8_t _txLength = 0;
    bool _txOverflow = false;
    bool _transmitting = false;

    uint8_t _rxBuffer[BUFFER_LENGTH];
    uint8_t _rxLength = 0;
    uint8_t _rxIndex = 0;

    void sdaLow();
    void sdaRelease();
    void sclLow();
    bool sclRelease();

    bool start();
    void stop();
    bool writeBit(bool bit);
    bool readBit(bool& bit, bool trace = false);
    bool writeByte(uint8_t data, bool& acked, bool traceAck = false);
    bool readByte(uint8_t& data, bool nack);

    void clampHold();
};

extern TwoWire Wire;
