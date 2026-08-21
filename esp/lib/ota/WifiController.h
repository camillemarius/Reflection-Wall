#pragma once

#include <Arduino.h>

class WifiController
{
public:
    bool begin();
    bool isConnected() const;
};