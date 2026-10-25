#include "wakeupReason.h"

#include <user_interface.h>
#include "pinMapping.h"
#include "DebugLogger.h"
#include "features.h"

namespace
{
    // Pegel, wie sie unmittelbar nach dem Reset gemessen
    // wurden. Nach dem Lesen des Expanders sind sie nicht mehr
    // rekonstruierbar, log() greift deshalb hierauf zurueck.
    int _hlkLevel = -1;
    int _expLevel = -1;
    uint32_t _rawReason = 0xFFFFFFFF;
}

WakeupReason::Reason WakeupReason::getReason()
{
    pinMode(Pins::INT_HLK, INPUT_PULLUP);
    pinMode(Pins::INT_GPIO_EXP, INPUT_PULLUP);

    _hlkLevel = digitalRead(Pins::INT_HLK);
    _expLevel = digitalRead(Pins::INT_GPIO_EXP);

    rst_info* resetInfo = ESP.getResetInfoPtr();

    _rawReason = (resetInfo != nullptr) ? resetInfo->reason : 0xFFFFFFFF;

    // Der Expander haelt INT auf LOW, bis gelesen wird. Liegt
    // die Leitung an, ist sie die Ursache - unabhaengig davon,
    // ob der Reset als Deep-Sleep-Wakeup oder als externer
    // Reset gemeldet wird. Beides erreicht den ESP ueber
    // denselben RST-Pin und wird nicht zuverlaessig
    // unterschieden.
    if (_expLevel == LOW)
        return Reason::INT_GPIO_EXP;

    // INT_HLK zaehlt nur mit Radar: ohne ihn liest der Pin wegen des
    // Pull-ups dauernd HIGH und jeder Timer-Wecker sah wie der Radar aus (R12).
    if (Features::RADAR_INSTALLED && _hlkLevel == HIGH && _rawReason != REASON_DEFAULT_RST)
        return Reason::INT_HLK;

    switch (_rawReason)
    {
        case REASON_DEFAULT_RST:
            return Reason::POWER_ON;

        case REASON_DEEP_SLEEP_AWAKE:
            return Reason::TIMER;

        case REASON_EXT_SYS_RST:
            return Reason::SHUTDOWN_BUTTON;

        default:
            return Reason::UNKNOWN;
    }
}

void WakeupReason::log(Reason reason)
{
    DebugSerial.printf("[WAKEUP] %s (Reset %s, INT_HLK=%s, INT_EXP=%s)\n",
                       toString(reason),
                       resetReasonRaw(),
                       _hlkLevel < 0 ? "?" : (_hlkLevel == HIGH ? "HIGH" : "LOW"),
                       _expLevel < 0 ? "?" : (_expLevel == HIGH ? "HIGH" : "LOW"));
}

const char* WakeupReason::toString(Reason reason)
{
    switch (reason)
    {
        case Reason::POWER_ON:
            return "Power On";

        case Reason::TIMER:
            return "Timer Wakeup";

        case Reason::INT_HLK:
            return "INT_HLK";

        case Reason::INT_GPIO_EXP:
            return "INT_GPIO_EXP";

        case Reason::SHUTDOWN_BUTTON:
            return "Externer Reset";

        case Reason::UNKNOWN:
        default:
            return "Unknown";
    }
}

const char* WakeupReason::resetReasonRaw()
{
    switch (_rawReason)
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
