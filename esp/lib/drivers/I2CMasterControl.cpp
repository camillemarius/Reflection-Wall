#include "I2CMasterControl.h"

#include <Arduino.h>
#include <Wire.h>

#include "pinMapping.h"


uint8_t I2CMasterControl::_recoveries = 0;


namespace
{
    // Rueckgabewerte von Wire.endTransmission(). Der Unterschied
    // zwischen 2 und 4 ist der entscheidende: 2 heisst, der Bus
    // funktioniert und niemand fuehlt sich angesprochen. 4 heisst,
    // die Uebertragung kam gar nicht zustande - dann liegt es am
    // Bus, nicht am Teilnehmer.
    const char* twiErrorName(uint8_t code)
    {
        switch (code)
        {
            case 1:  return "Daten zu lang";
            case 2:  return "NACK auf Adresse";
            case 3:  return "NACK auf Daten";
            case 4:  return "Busfehler / Timeout";
            default: return "unbekannt";
        }
    }
}


void I2CMasterControl::scan(Print& output, uint8_t passes)
{
    if (passes == 0)
        passes = 1;

    for (uint8_t pass = 1; pass <= passes; pass++)
    {
        output.print("I2C Scan, Durchlauf ");
        output.print(pass);
        output.print('/');
        output.println(passes);

        // Haengt hier eine Leitung auf LOW, ist jede weitere
        // Aussage wertlos - dann ist der Bus blockiert.
        output.print("  Ruhepegel  SDA=");
        output.print(digitalRead(Pins::I2C_SDA));
        output.print(" SCL=");
        output.println(digitalRead(Pins::I2C_SCL));

        uint8_t  found = 0;
        uint16_t codeCount[5] = { 0, 0, 0, 0, 0 };

        output.print("  Gefunden  ");

        for (uint8_t address = 0x03; address <= 0x77; address++)
        {
            Wire.beginTransmission(address);

            const uint8_t code = Wire.endTransmission();

            if (code == 0)
            {
                output.print(" 0x");
                if (address < 0x10)
                    output.print('0');
                output.print(address, HEX);
                found++;
                continue;
            }

            codeCount[code <= 4 ? code : 0]++;
        }

        if (found == 0)
            output.print("keine");

        output.println();

        for (uint8_t code = 1; code <= 4; code++)
        {
            if (codeCount[code] == 0)
                continue;

            output.print("  ");
            output.print(codeCount[code]);
            output.print("x Code ");
            output.print(code);
            output.print(" (");
            output.print(twiErrorName(code));
            output.println(")");
        }

        if (codeCount[0] != 0)
        {
            output.print("  ");
            output.print(codeCount[0]);
            output.println("x Code >4 (unbekannt)");
        }
    }
}



void I2CMasterControl::begin()
{
    pinMode(Pins::I2C_MASTER_SEL, OUTPUT);
    
    // Standard:
    // anderer Master hat Kontrolle
    digitalWrite(Pins::I2C_MASTER_SEL, LOW);

    Wire.begin(Pins::I2C_SDA, Pins::I2C_SCL);

    // Reduzierte Taktrate: stabiler bei langen Leitungen / schwachen Pull-Ups
    Wire.setClock(I2C_CLOCK_HZ);
}



void I2CMasterControl::enable()
{
    // ESP bekommt I2C Zugriff
    digitalWrite(Pins::I2C_MASTER_SEL, HIGH);

    // Analog Switch Einschwingzeit
    delayMicroseconds(SETTLE_US);

    // Ein Teilnehmer, der mitten in einem gestoerten Byte
    // stehen geblieben ist, haelt SDA fest - dann scheitert
    // jeder weitere Zugriff.
    if (digitalRead(Pins::I2C_SDA) == LOW)
        _recoveries += recoverBus() ? 1 : 0;
}



// Taktet SCL bis zu neunmal, bis der haengende Teilnehmer sein
// Byte zu Ende geschoben hat und SDA loslaesst, und schliesst
// mit einer STOP-Bedingung ab.
bool I2CMasterControl::recoverBus()
{
    constexpr uint32_t HALF_PERIOD_US = 50;

    pinMode(Pins::I2C_SDA, INPUT_PULLUP);
    pinMode(Pins::I2C_SCL, OUTPUT_OPEN_DRAIN);

    for (uint8_t i = 0; i < 9 && digitalRead(Pins::I2C_SDA) == LOW; i++)
    {
        digitalWrite(Pins::I2C_SCL, LOW);
        delayMicroseconds(HALF_PERIOD_US);
        digitalWrite(Pins::I2C_SCL, HIGH);
        delayMicroseconds(HALF_PERIOD_US);
    }

    // STOP: SDA steigt, waehrend SCL HIGH ist
    pinMode(Pins::I2C_SDA, OUTPUT_OPEN_DRAIN);
    digitalWrite(Pins::I2C_SCL, LOW);
    delayMicroseconds(HALF_PERIOD_US);
    digitalWrite(Pins::I2C_SDA, LOW);
    delayMicroseconds(HALF_PERIOD_US);
    digitalWrite(Pins::I2C_SCL, HIGH);
    delayMicroseconds(HALF_PERIOD_US);
    digitalWrite(Pins::I2C_SDA, HIGH);
    delayMicroseconds(HALF_PERIOD_US);

    const bool released = digitalRead(Pins::I2C_SDA) == HIGH;

    Wire.begin(Pins::I2C_SDA, Pins::I2C_SCL);
    Wire.setClock(I2C_CLOCK_HZ);

    return released;
}



uint8_t I2CMasterControl::recoveryCount()
{
    return _recoveries;
}



void I2CMasterControl::disable()
{
    // Analog Switch Einschwingzeit
    delayMicroseconds(SETTLE_US);

    // Bus wieder freigeben
    digitalWrite(Pins::I2C_MASTER_SEL,LOW);
}



bool I2CMasterControl::waitForIdleBus()
{
    const uint32_t start = micros();

    while (digitalRead(Pins::I2C_SDA) == LOW ||
           digitalRead(Pins::I2C_SCL) == LOW)
    {
        if (micros() - start > BUS_IDLE_TIMEOUT_US)
            return false;
    }

    return true;
}