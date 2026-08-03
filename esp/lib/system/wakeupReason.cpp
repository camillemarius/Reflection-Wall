#include "WakeupReason.h"

#include <user_interface.h>
#include "pinMapping.h"

WakeupReason::Reason WakeupReason::getReason()
{
    pinMode(Pins::INT_HLK, INPUT_PULLUP);
    pinMode(Pins::INT_GPIO_EXP, INPUT_PULLUP);

    rst_info* resetInfo = ESP.getResetInfoPtr();

    if (resetInfo->reason == REASON_DEEP_SLEEP_AWAKE)
    {
        if (digitalRead(Pins::INT_HLK) == HIGH)
            return Reason::INT_HLK;

        if (digitalRead(Pins::INT_GPIO_EXP) == LOW)
            return Reason::INT_GPIO_EXP;

        return Reason::TIMER;
    }

    if (resetInfo->reason == REASON_EXT_SYS_RST)
        return Reason::SHUTDOWN_BUTTON;

    return Reason::UNKNOWN;
}

const char* WakeupReason::toString(Reason reason)
{
    switch (reason)
    {
        case Reason::TIMER:
            return "Timer Wakeup";

        case Reason::INT_HLK:
            return "INT_HLK";

        case Reason::INT_GPIO_EXP:
            return "INT_GPIO_EXP";

        case Reason::SHUTDOWN_BUTTON:
            return "Shutdown Button";

        case Reason::UNKNOWN:
        default:
            return "Unknown";
    }
}

const char* WakeupReason::resetReasonRaw()
{
    rst_info* resetInfo = ESP.getResetInfoPtr();

    switch (resetInfo->reason)
    {
        case REASON_DEFAULT_RST:
            return "DEFAULT_RST";

        case REASON_WDT_RST:
            return "WATCHDOG";

        case REASON_EXCEPTION_RST:
            return "EXCEPTION";

        case REASON_SOFT_WDT_RST:
            return "SOFT_WDT";

        case REASON_SOFT_RESTART:
            return "SOFT_RESTART";

        case REASON_EXT_SYS_RST:
            return "EXT_SYS_RST";

        case REASON_DEEP_SLEEP_AWAKE:
            return "DEEP_SLEEP_AWAKE";

        default:
            return "UNKNOWN_RESET";
    }
}