#include "I2CMasterControl.h"

#include <Arduino.h>
#include <Wire.h>

#include "pinMapping.h"


void I2CMasterControl::scan(Print& output)
{
    Wire.begin(Pins::I2C_SDA, Pins::I2C_SCL);
    //Wire.setClock(5000);

    output.println("I2C scan:");

    uint8_t found = 0;
    for (uint8_t address = 0x03; address <= 0x77; address++)
    {
        Wire.beginTransmission(address);
        if (Wire.endTransmission() == 0)
        {
            output.print("  0x");
            if (address < 0x10)
                output.print('0');
            output.println(address, HEX);
            found++;
        }
    }

    if (found == 0)
        output.println("  Keine I2C-Adressen gefunden");
}



void I2CMasterControl::begin()
{
    pinMode(
        Pins::I2C_MASTER_SEL,
        OUTPUT
    );


    // Standard:
    // anderer Master hat Kontrolle
    digitalWrite(
        Pins::I2C_MASTER_SEL,
        LOW
    );
}



void I2CMasterControl::enable()
{
    // ESP bekommt I2C Zugriff
    digitalWrite(
        Pins::I2C_MASTER_SEL,
        HIGH
    );


    // Analog Switch Einschwingzeit
    //delayMicroseconds(100);
    delay(1000);
}



void I2CMasterControl::disable()
{
    // Analog Switch Einschwingzeit
    //delayMicroseconds(100);
    delay(1000);
    // Bus wieder freigeben
    digitalWrite(
        Pins::I2C_MASTER_SEL,
        LOW
    );
}