#include "I2CMasterControl.h"

#include <Arduino.h>
<<<<<<< HEAD
#include <Wire.h>
=======
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61

#include "pinMapping.h"


<<<<<<< HEAD
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


=======
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61

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
<<<<<<< HEAD
    //delayMicroseconds(100);
    delay(1000);
=======
    delayMicroseconds(10);
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61
}



void I2CMasterControl::disable()
{
<<<<<<< HEAD
    // Analog Switch Einschwingzeit
    //delayMicroseconds(100);
    delay(1000);
=======
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61
    // Bus wieder freigeben
    digitalWrite(
        Pins::I2C_MASTER_SEL,
        LOW
    );
}