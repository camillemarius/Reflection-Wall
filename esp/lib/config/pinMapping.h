#pragma once

#include <Arduino.h>

namespace Pins
{
    // Wakeup Pins
    constexpr uint8_t INT_HLK       = 13;   // GPIO13
    constexpr uint8_t INT_GPIO_EXP  = 14;   // GPIO14

    // I2C Pins
    constexpr uint8_t I2C_SDA       = 4;    // GPIO4
    constexpr uint8_t I2C_SCL       = 5;    // GPIO5

    // rpi Power Switch
    constexpr uint8_t ESP_GPIO12_PS = 12;   // GPIO12

    // I2C Master Selection
    constexpr uint8_t I2C_MASTER_SEL = 15; // GPIO15
}