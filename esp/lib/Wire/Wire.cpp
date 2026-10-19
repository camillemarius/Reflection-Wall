#include "Wire.h"

namespace
{
    constexpr uint32_t DEFAULT_CLOCK_HZ = 100000;
}

TwoWire Wire;


// ---------------------------------------------------------
// Einrichtung
// ---------------------------------------------------------

void TwoWire::begin(int sda, int scl)
{
    _sda = sda;
    _scl = scl;

    // Erst den Ausgang auf "frei" setzen, dann den Modus: in der
    // umgekehrten Reihenfolge zoege der Pin kurz auf LOW.
    digitalWrite(_sda, HIGH);
    digitalWrite(_scl, HIGH);
    pinMode(_sda, OUTPUT_OPEN_DRAIN);
    pinMode(_scl, OUTPUT_OPEN_DRAIN);

    _busHeld = false;

    if (_halfPeriodUs == 0)
        setClock(DEFAULT_CLOCK_HZ);
}


void TwoWire::begin()
{
    begin(SDA, SCL);
}


void TwoWire::setClock(uint32_t frequency)
{
    if (frequency == 0)
        frequency = DEFAULT_CLOCK_HZ;

    _halfPeriodUs = 500000UL / frequency;

    if (_halfPeriodUs < 2)
        _halfPeriodUs = 2;

    clampHold();
}


void TwoWire::setClockStretchLimit(uint32_t limitUs)
{
    _stretchLimitUs = limitUs;
}


void TwoWire::setSdaHold(uint32_t holdUs)
{
    _holdUs = holdUs;
    clampHold();
}


// Die Hold-Zeit ist Teil der Low-Phase von SCL; sie darf die
// halbe Periode nicht auffressen, sonst bleibt fuer die
// Setup-Zeit vor der steigenden Flanke nichts uebrig.
void TwoWire::clampHold()
{
    if (_holdUs >= _halfPeriodUs)
        _holdUs = _halfPeriodUs - 1;
}


// ---------------------------------------------------------
// Pins (Open Drain: LOW treibt, HIGH gibt frei)
// ---------------------------------------------------------

void TwoWire::sdaLow()     { digitalWrite(_sda, LOW); }
void TwoWire::sdaRelease() { digitalWrite(_sda, HIGH); }
void TwoWire::sclLow()     { digitalWrite(_scl, LOW); }


// Gibt SCL frei und wartet, bis die Leitung wirklich high ist
// (Clock Stretching eines Slaves oder langsame Flanke).
bool TwoWire::sclRelease()
{
    digitalWrite(_scl, HIGH);

    const uint32_t start = micros();

    while (digitalRead(_scl) == LOW)
    {
        if (micros() - start > _stretchLimitUs)
            return false;
    }

    return true;
}


// ---------------------------------------------------------
// Bus-Bedingungen
// ---------------------------------------------------------
// Alle Bits enden mit SCL high. Jede Aenderung an SDA
// passiert deshalb erst nach "SCL low" + Hold-Zeit - nur
// START und STOP veraendern SDA bewusst bei SCL high.

bool TwoWire::start()
{
    // Repeated Start: aus der Mitte eines Transfers heraus SDA
    // bei SCL low freigeben, dann SCL wieder hoch
    if (_busHeld)
    {
        sclLow();
        delayMicroseconds(_holdUs);
        sdaRelease();
        delayMicroseconds(_halfPeriodUs - _holdUs);

        if (!sclRelease())
            return false;

        delayMicroseconds(_halfPeriodUs);
        _busHeld = false;
    }

    sdaRelease();

    if (!sclRelease())
        return false;

    // Haelt jemand SDA fest, ist der Bus nicht frei
    if (digitalRead(_sda) == LOW)
        return false;

    delayMicroseconds(_halfPeriodUs);

    // START: SDA faellt, waehrend SCL high ist. SCL faellt erst
    // im ersten writeBit(), eine halbe Periode spaeter.
    sdaLow();
    _tStartUs = micros();
    delayMicroseconds(_halfPeriodUs);

    return true;
}


void TwoWire::stop()
{
    // SDA zuerst auf LOW bringen - aber erst, wenn SCL sicher
    // low ist, sonst saehe ein Slave ein START
    sclLow();
    delayMicroseconds(_holdUs);
    sdaLow();
    delayMicroseconds(_halfPeriodUs - _holdUs);

    // Auch bei SCL-Timeout SDA freigeben, damit der Bus nicht
    // vom ESP festgehalten wird
    sclRelease();
    delayMicroseconds(_halfPeriodUs);

    // STOP: SDA steigt, waehrend SCL high ist
    sdaRelease();
    delayMicroseconds(_halfPeriodUs);

    _busHeld = false;
}


bool TwoWire::writeBit(bool bit)
{
    sclLow();
    delayMicroseconds(_holdUs);

    if (bit)
        sdaRelease();
    else
        sdaLow();

    delayMicroseconds(_halfPeriodUs - _holdUs);

    if (!sclRelease())
        return false;

    delayMicroseconds(_halfPeriodUs);
    return true;
}


// Tastet SDA waehrend einer halben Periode ab (Diagnose). Liefert
// die Samples als Bitmaske (Bit n = Sample n war HIGH).
static uint64_t sampleSda(int sda, uint32_t durationUs, uint8_t& count,
                          int releasePin = -1, uint32_t releaseAtUs = 0)
{
    uint64_t trace = 0;
    count = 0;
    bool released = (releasePin < 0);

    const uint32_t start = micros();

    while (micros() - start < durationUs)
    {
        if (!released && micros() - start >= releaseAtUs)
        {
            digitalWrite(releasePin, HIGH);
            released = true;
        }

        if (count < 64)
        {
            if (GPIP(sda))
                trace |= (1ULL << count);
            count++;
        }

        delayMicroseconds(1);
    }

    if (!released)
        digitalWrite(releasePin, HIGH);

    return trace;
}


bool TwoWire::readBit(bool& bit, bool trace)
{
    // SDA erst nach der Hold-Zeit freigeben. Direkt vor dem ACK
    // ist das der kritische Moment: war das letzte Bit eine 0,
    // waere ein zu fruehes Freigeben ein STOP.
    sclLow();

    if (trace)
    {
        // Direkt nach "SCL low" 64 Samples so schnell wie moeglich
        // (ohne Pausen) - so wird auch ein nur kurz sichtbares ACK
        // erfasst. SDA ist hier nach einem Bit 0 = 1 schon frei.
        const uint32_t startCycles = ESP.getCycleCount();
        uint64_t fast = 0;

        for (uint8_t i = 0; i < 64; i++)
        {
            if (GPIP(_sda))
                fast |= (1ULL << i);

            for (volatile uint8_t d = 0; d < 4; d++) { }
        }

        _traceFastCycles = ESP.getCycleCount() - startCycles;
        _traceLow = fast;
        _traceLowCount = 64;

        // Rest der Low-Phase wie im Normalfall
        const uint32_t usedUs = _traceFastCycles / (F_CPU / 1000000);

        if (usedUs < _holdUs)
            delayMicroseconds(_holdUs - usedUs);

        sdaRelease();

        if (usedUs < _halfPeriodUs)
            delayMicroseconds(_halfPeriodUs - (usedUs > _holdUs ? usedUs : _holdUs));
    }
    else
    {
        delayMicroseconds(_holdUs);
        sdaRelease();
        delayMicroseconds(_halfPeriodUs - _holdUs);
    }

    if (!sclRelease())
        return false;

    bit = (digitalRead(_sda) == HIGH);

    if (trace)
        _traceHigh = sampleSda(_sda, _halfPeriodUs, _traceHighCount);
    else
        delayMicroseconds(_halfPeriodUs);

    return true;
}


bool TwoWire::writeByte(uint8_t data, bool& acked, bool traceAck)
{
    for (uint8_t i = 0; i < 8; i++)
    {
        if (!writeBit(data & 0x80))
            return false;

        data <<= 1;
    }

    // Zeitpunkt der fallenden SCL-Flanke vor dem ACK (Diagnose):
    // readBit() beginnt mit sclLow()
    _tAckFallUs = micros();

    bool nack;
    if (!readBit(nack, traceAck))
        return false;

    acked = !nack;
    return true;
}


bool TwoWire::readByte(uint8_t& data, bool nack)
{
    data = 0;

    for (uint8_t i = 0; i < 8; i++)
    {
        bool bit;
        if (!readBit(bit))
            return false;

        data = (data << 1) | (bit ? 1 : 0);
    }

    return writeBit(nack);
}


// ---------------------------------------------------------
// Master: Schreiben
// ---------------------------------------------------------

void TwoWire::beginTransmission(uint8_t address)
{
    _txAddress = address;
    _txLength = 0;
    _txOverflow = false;
    _transmitting = true;
}


size_t TwoWire::write(uint8_t data)
{
    if (!_transmitting)
        return 0;

    if (_txLength >= BUFFER_LENGTH)
    {
        _txOverflow = true;
        return 0;
    }

    _txBuffer[_txLength++] = data;
    return 1;
}


size_t TwoWire::write(const uint8_t* data, size_t length)
{
    size_t written = 0;

    for (size_t i = 0; i < length; i++)
        written += write(data[i]);

    return written;
}


uint8_t TwoWire::endTransmission(uint8_t sendStop)
{
    _transmitting = false;

    if (_txOverflow)
        return 1;

    if (!start())
        return 4;

    bool acked;

    if (!writeByte(_txAddress << 1, acked))
    {
        stop();
        return 4;
    }

    if (!acked)
    {
        stop();
        return 2;
    }

    bool dataNacked = false;

    for (uint8_t i = 0; i < _txLength; i++)
    {
        if (!writeByte(_txBuffer[i], acked, _ackTrace))
        {
            stop();
            return 4;
        }

        if (!acked)
        {
            if (!_ignoreDataNack)
            {
                stop();
                return 3;
            }

            dataNacked = true;
        }
    }

    if (dataNacked)
    {
        stop();
        return 3;
    }

    if (sendStop)
        stop();
    else
        _busHeld = true;

    return 0;
}


// ---------------------------------------------------------
// Master: Lesen
// ---------------------------------------------------------

uint8_t TwoWire::requestFrom(uint8_t address, uint8_t quantity, uint8_t sendStop)
{
    _rxLength = 0;
    _rxIndex = 0;

    if (quantity > BUFFER_LENGTH)
        quantity = BUFFER_LENGTH;

    if (quantity == 0)
        return 0;

    if (!start())
        return 0;

    bool acked;

    if (!writeByte((address << 1) | 0x01, acked) || !acked)
    {
        stop();
        return 0;
    }

    for (uint8_t i = 0; i < quantity; i++)
    {
        // Das letzte Byte wird mit NACK quittiert
        const bool last = (i == quantity - 1);

        if (!readByte(_rxBuffer[i], last))
        {
            stop();
            _rxLength = i;
            return i;
        }
    }

    if (sendStop)
        stop();
    else
        _busHeld = true;

    _rxLength = quantity;
    return quantity;
}


int TwoWire::available()
{
    return _rxLength - _rxIndex;
}


int TwoWire::read()
{
    if (_rxIndex >= _rxLength)
        return -1;

    return _rxBuffer[_rxIndex++];
}


int TwoWire::peek()
{
    if (_rxIndex >= _rxLength)
        return -1;

    return _rxBuffer[_rxIndex];
}


void TwoWire::flush()
{
    _rxLength = 0;
    _rxIndex = 0;
    _txLength = 0;
    _txOverflow = false;
}
