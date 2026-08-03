#pragma once

#include <Arduino.h>

class I2CMasterControl
{
public:

    static void begin();

    /**
     * Schaltet den ESP8266 als I2C Master ein
     */
    static void enable();


    /**
     * Gibt den I2C Bus wieder frei
     */
    static void disable();
};