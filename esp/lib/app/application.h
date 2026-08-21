#pragma once

#include "UartHandler.h"
#include "TextStorage.h"
#include "Display.h"
#include "PiCommunication.h"
#include "WakeupReason.h"

#include "PCF8575.h"
#include "InputManager.h"
<<<<<<< HEAD
#include "WifiController.h"
=======
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61

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
<<<<<<< HEAD

    WifiController _wifi;
=======
>>>>>>> a162efaed06d915565e2865b0a8f8b0f4a333a61
};