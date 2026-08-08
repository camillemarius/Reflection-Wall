#pragma once

#include "UartHandler.h"
#include "TextStorage.h"
#include "Display.h"
#include "PiCommunication.h"
#include "WakeupReason.h"

#include "PCF8575.h"
#include "InputManager.h"

class Application
{
public:
    Application();

    void begin();
    void loop();

private:
    void handleWakeup(WakeupReason::Reason reason);

    UartHandler _uart;
    TextStorage _storage;
    Display _display;
    piCommunication _pi;

    PCF8575 _gpioExpander;
    InputManager _inputs;
    
    WakeupReason::Reason _wakeupReason;
};