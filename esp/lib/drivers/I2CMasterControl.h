#pragma once

#include <Arduino.h>

class I2CMasterControl
{
public:

    static void begin();

<<<<<<< HEAD
    static void scan(Print& output);

=======
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61
    /**
     * Schaltet den ESP8266 als I2C Master ein
     */
    static void enable();


    /**
     * Gibt den I2C Bus wieder frei
     */
    static void disable();
};