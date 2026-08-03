#include "I2CMasterControl.h"

#include <Arduino.h>

#include "pinMapping.h"



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
    delayMicroseconds(10);
}



void I2CMasterControl::disable()
{
    // Bus wieder freigeben
    digitalWrite(
        Pins::I2C_MASTER_SEL,
        LOW
    );
}