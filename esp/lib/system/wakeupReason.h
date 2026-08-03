#pragma once

#include <Arduino.h>

class WakeupReason
{
public:
    enum class Reason
    {
        TIMER,
        INT_HLK,
        INT_GPIO_EXP,
        SHUTDOWN_BUTTON,
        UNKNOWN
    };

    static Reason getReason();
    static const char* toString(Reason reason);
    static const char* resetReasonRaw();
};