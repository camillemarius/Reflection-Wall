#include "PowerSwitchPin.h"
#include "pinMapping.h"

#include <Arduino.h>

// Als Eingang lesen: hochohmig, der Pegel ist der, den die Leitung fuehrt.
bool PowerSwitchPin::readIdle()
{
    pinMode(Pins::ESP_GPIO12_PS, INPUT);
    return digitalRead(Pins::ESP_GPIO12_PS) != LOW;
}

// digitalWrite() setzt beim ESP8266 das Ausgangsregister schon im
// Eingangsmodus. In der umgekehrten Reihenfolge wuerde
// pinMode(OUTPUT) den Pin kurz auf LOW ziehen.
void PowerSwitchPin::drive(bool high)
{
    digitalWrite(Pins::ESP_GPIO12_PS, high ? HIGH : LOW);
    pinMode(Pins::ESP_GPIO12_PS, OUTPUT);
}

void PowerSwitchPin::waitMs(unsigned long ms)
{
    delay(ms);
}
