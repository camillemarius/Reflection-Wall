#pragma once

#include "PiPower.h"

// GPIO12 (Pins::ESP_GPIO12_PS) zum Flipflop der Pi-Speisung.
// Der Pin bleibt Eingang, bis readIdle()/drive() ihn anfassen.
class PowerSwitchPin : public IPowerPin
{
public:
    bool readIdle() override;
    void drive(bool high) override;
    void waitMs(unsigned long ms) override;
};
