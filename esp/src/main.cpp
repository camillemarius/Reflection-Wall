#include <Arduino.h>

#include "application.h"

Application application;

void setup()
{
    application.begin();
}

void loop()
{
    application.loop();
}